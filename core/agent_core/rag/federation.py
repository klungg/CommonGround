import os
import yaml
import asyncio
import logging
from typing import Dict, List, Any, Optional

# Import from the refactored duckdb_api.py
from .duckdb_api import DuckDBRAGStore
from .search_engine import get_search_config_details

logger = logging.getLogger(__name__)

class RAGEngine:
    """Represents a single, configured RAG data source."""
    def __init__(self, config_path: str):
        # 1. Use the existing get_search_config_details to load and validate the configuration
        self.config = get_search_config_details(config_path)
        if not self.config:
            raise ValueError(f"Failed to load or validate configuration from {config_path}.")
            
        # 2. Get key information from the configuration
        self.source_name = self.config['source_name']
        self.is_writable = self.config.get('database_writable', False)
        self.description = self.config.get('description', 'No description provided.')
        self.is_global = self.config.get('is_global', False)
        
        # 3. Create a DuckDBRAGStore instance for this data source
        self.db_store = DuckDBRAGStore(config=self.config)
        logger.info("rag_engine_initialized", extra={"source_name": self.source_name, "is_writable": self.is_writable})

    async def search(self, query_text: str, project_id: str, top_k: int, tags: Optional[List[str]] = None) -> List[Dict]:
        """Performs a search on this engine."""
        try:
            results = await self.db_store.vector_search_text(query_text, project_id, top_k, tags)
            # Inject the source name into each result for upstream differentiation
            for result in results:
                result['source'] = self.source_name
            return results
        except Exception as e:
            logger.error("rag_engine_search_error", extra={"source_name": self.source_name, "error": str(e)}, exc_info=True)
            return []

class _RAGFederationService:
    """A singleton service that manages and queries multiple RAG engines."""
    _instance = None

    def __init__(self):
        self.engines: Dict[str, RAGEngine] = {}
        self.default_writable_source_name: Optional[str] = None
        self._load_configs()

    def _load_configs(self):
        """Loads all configurations from the rag_configs/ directory."""
        index_path = 'rag_configs/index.yaml'
        if not os.path.exists(index_path):
            logger.error("main_rag_config_file_not_found", extra={"index_path": index_path})
            return
        
        with open(index_path, 'r', encoding='utf-8') as f:
            index_config = yaml.safe_load(f)
        
        self.default_writable_source_name = index_config.get('default_writable_source')
        
        config_dir = os.path.dirname(index_path)
        
        for source_name in index_config.get('active_sources', []):
            config_path = os.path.join(config_dir, f"{source_name}.yaml")
            if os.path.exists(config_path):
                try:
                    self.engines[source_name] = RAGEngine(config_path)
                except Exception as e:
                    logger.error("rag_engine_load_failed", extra={"source_name": source_name, "error": str(e)}, exc_info=True)
            else:
                logger.warning("rag_config_file_not_found", extra={"config_path": config_path, "source_name": source_name})

    async def search_all(self, query_text: str, project_id: str, top_k: int, tags: Optional[List[str]] = None, sources: Optional[List[str]] = None) -> List[Dict]:
        """Concurrently searches on all active engines, then merges and re-ranks the results."""
        if not self.engines:
            logger.warning("No RAG engines loaded, search will return empty results.")
            return []
        engines_to_query = []
        if sources and isinstance(sources, list):
            logger.info("rag_search_scoped_to_sources", extra={"sources": sources})
            for source_name in sources:
                if source_name in self.engines:
                    engines_to_query.append(self.engines[source_name])
                else:
                    logger.warning("rag_source_not_found_or_inactive", extra={"source_name": source_name})
        else:
            # If sources is None or empty, search all engines
            logger.info("RAG search running on all active sources.")
            engines_to_query = list(self.engines.values())
        if not engines_to_query:
            logger.warning("No RAG engines available for query (requested sources may not exist).")
            return []
         
        search_tasks = [engine.search(query_text, project_id, top_k, tags) for engine in engines_to_query]
        all_results_nested = await asyncio.gather(*search_tasks)
        
        # Flatten the list of lists of results into a single list
        flat_results = [item for sublist in all_results_nested for item in sublist]
        
        # Sort by 'similarity' score in descending order
        sorted_results = sorted(flat_results, key=lambda x: x.get('similarity', 0.0), reverse=True)
        
        return sorted_results[:top_k]

    def get_writable_engine(self) -> Optional[RAGEngine]:
        """Gets the default writable engine instance."""
        if self.default_writable_source_name:
            engine = self.engines.get(self.default_writable_source_name)
            if engine and engine.is_writable:
                return engine
            elif engine:
                logger.error("default_writable_source_is_readonly", extra={"source_name": self.default_writable_source_name})
                return None
        
        # If no default is specified, find the first writable engine as a fallback
        for engine in self.engines.values():
            if engine.is_writable:
                logger.warning("falling_back_to_first_writable_source", extra={"source_name": engine.source_name})
                return engine
                
        return None
    
    def get_source_details(self) -> List[Dict[str, Any]]:
        """Gets a list of details for all loaded data sources, for use by tools."""
        if not self.engines:
            return []
        
        details_list = []
        for source_name, engine in self.engines.items():
            details_list.append({
                "name": engine.source_name,
                "description": engine.description,
                "is_global": engine.is_global,
                "is_writable": engine.is_writable
            })
        return details_list
    
# Create a global singleton for other modules to import and use
RAGFederationService = _RAGFederationService()