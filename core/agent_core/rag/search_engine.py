import yaml
import duckdb
from typing import List, Dict, Any, Optional
import os
import logging
from .embedding_utils import fast_8bit_uniform_scalar_quantize, fast_4bit_uniform_scalar_quantize

logger = logging.getLogger(__name__)

_DB_CONNECTION_CACHE = {}

SCALAR_QUANTIZATION_LIMIT_8BIT = 0.3
SCALAR_QUANTIZATION_LIMIT_4BIT = 0.18

def get_db_connection(db_file: str, read_only: bool) -> duckdb.DuckDBPyConnection:
    """Get a cached database connection, transparently handling read-only upgrades."""
    if db_file in _DB_CONNECTION_CACHE:
        conn, is_read_only = _DB_CONNECTION_CACHE[db_file]
        
        # If a writable connection is requested, but we have a read-only one, we need to upgrade.
        if not read_only and is_read_only:
            logger.info("reopening_db_connection_for_write_access", extra={"db_file": db_file})
            conn.close()
            # Remove from cache to force re-creation below
            del _DB_CONNECTION_CACHE[db_file]
        else:
            # Existing connection is sufficient (either writable, or read-only and read-only was requested)
            return conn

    # No connection exists in cache, or it was closed for upgrade. Create a new one.
    try:
        logger.info("caching_new_db_connection", extra={"db_file": db_file, "read_only": read_only})
        conn = duckdb.connect(database=db_file, read_only=read_only)
        _DB_CONNECTION_CACHE[db_file] = (conn, read_only)
        return conn
    except duckdb.Error as e:
        logger.error("duckdb_connection_failed", extra={"db_file": db_file, "error": str(e)})
        raise

def load_search_config(config_path: str) -> Dict[str, Any]:
    """Load search configuration from a YAML file."""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        if not isinstance(config, dict):
            raise ValueError("Configuration file content is not a valid YAML dictionary.")
        return config
    except FileNotFoundError:
        logger.error("search_config_not_found", extra={"config_path": config_path})
        raise
    except yaml.YAMLError as e:
        logger.error("search_config_parse_failed", extra={"config_path": config_path, "error": str(e)})
        raise
    except Exception as e:
        logger.error("search_config_load_unknown_error", extra={"config_path": config_path, "error": str(e)})
        raise

def get_search_config_details(config_path: str) -> Optional[Dict[str, Any]]:
    """
    Load, parse, and validate search configuration details.
    """
    try:
        config = load_search_config(config_path)
    except Exception:
        return None

    details = {}
    details["database_writable"] = config.get("database_writable", False)
    details["description"] = config.get("description", 'No description provided.')
    details["is_global"] = config.get("is_global", False)
    db_file_path = config.get("database_file")
    
    if db_file_path:
        if not os.path.isabs(db_file_path):
            config_dir = os.path.dirname(os.path.abspath(config_path))
            details["database_file"] = os.path.join(config_dir, db_file_path)
        else:
            details["database_file"] = db_file_path
    else:
        details["database_file"] = None
    
    meta_table_config = config.get("meta_table", {})
    embedding_table_config = config.get("embedding_table", {})

    # Directly add the complete sub-dictionaries to details for use by DuckDBRAGStore
    details["meta_table"] = meta_table_config
    details["embedding_table"] = embedding_table_config

    if not details["database_file"] or not meta_table_config or not embedding_table_config:
        logger.error("search_config_missing_required_keys", extra={"config_path": config_path})
        return None

    details["meta_table_name"] = meta_table_config.get("name")
    details["meta_id_col"] = meta_table_config.get("id_column")
    details["meta_text_col"] = meta_table_config.get("text_column")
    details["meta_tags_col"] = meta_table_config.get("tags_column")
    meta_retrieval_cols = meta_table_config.get("retrieval_columns", [])
    details["direct_search_columns"] = meta_table_config.get("direct_search_columns", [])

    if not details["meta_table_name"] or not details["meta_id_col"]:
        logger.error("search_config_meta_table_misconfigured", extra={"config_path": config_path})
        return None

    all_meta_retrieval_cols = []
    if details["meta_text_col"]:
        all_meta_retrieval_cols.append(details["meta_text_col"])
    for col in meta_retrieval_cols:
        if col not in all_meta_retrieval_cols:
            all_meta_retrieval_cols.append(col)
    details["all_meta_retrieval_cols"] = all_meta_retrieval_cols
    
    details["emb_table_name"] = embedding_table_config.get("name")
    details["emb_id_col"] = embedding_table_config.get("id_column")
    details["emb_vector_col"] = embedding_table_config.get("embedding_column")
    details["emb_model_id"] = embedding_table_config.get("emb_model_id")

    details["model_config_params"] = embedding_table_config.get("model_config_params")
    details["quantization"] = embedding_table_config.get("quantization")
    details["emb_mrl_dims"] = embedding_table_config.get("mrl_dims")
    details["query_task_type"] = embedding_table_config.get("query_task_type")
    details["source_name"] = config.get("source_name")

    if not all([details["emb_table_name"], details["emb_id_col"], details["emb_vector_col"], details["emb_model_id"]]):
        logger.error("search_config_embedding_table_misconfigured", extra={"config_path": config_path})
        return None
    
    if details["meta_id_col"] != details["emb_id_col"]:
        logger.warning("search_config_id_column_mismatch", extra={"config_path": config_path})

    return details

def search_similar_documents(
    query_text: str,
    search_config_details: Dict[str, Any],
    top_k: int = 10,
    tags: Optional[List[str]] = None,
    model_instance: Optional[Any] = None
) -> List[Dict[str, Any]]:
    """
    Searches for similar documents using vector search.
    """
    if not query_text:
        return []

    db_file = search_config_details["database_file"]
    meta_table_name = search_config_details["meta_table_name"]
    meta_id_col = search_config_details["meta_id_col"]
    meta_tags_col = search_config_details["meta_tags_col"]
    all_meta_retrieval_cols = search_config_details["all_meta_retrieval_cols"]
    emb_table_name = search_config_details["emb_table_name"]
    emb_id_col = search_config_details["emb_id_col"]
    emb_mrl_dims = search_config_details["emb_mrl_dims"]
    query_task_type = search_config_details["query_task_type"]

    if model_instance is None:
        raise ValueError("A valid EmbeddingProvider instance must be provided.")

    try:
        query_embedding_array = model_instance.generate_embedding([query_text], task_type=query_task_type, mrl=emb_mrl_dims)
        if query_embedding_array is None or len(query_embedding_array) == 0:
            logger.error("query_embedding_generation_failed")
            return []

        quantization = search_config_details.get("quantization")
        if quantization == "int8":
            vec_int8 = fast_8bit_uniform_scalar_quantize(query_embedding_array, SCALAR_QUANTIZATION_LIMIT_8BIT)
            query_embedding = vec_int8.tolist()[0]
        elif quantization == "int4":
            vec_int4 = fast_4bit_uniform_scalar_quantize(query_embedding_array, SCALAR_QUANTIZATION_LIMIT_4BIT)
            query_embedding = vec_int4.tolist()[0]
        else:
            query_embedding = query_embedding_array[0].tolist()
    except Exception as e:
        logger.error("query_embedding_generation_exception", extra={"error": str(e)})
        return []

    conn = get_db_connection(db_file, read_only=True)
    try:
        select_clause = ", ".join(list(dict.fromkeys([f'meta."{meta_id_col}" AS "{meta_id_col}"'] + [f'meta."{col}" AS "{col}"' for col in all_meta_retrieval_cols if col != meta_id_col])))

        emb_vector_col_config = search_config_details["emb_vector_col"]
        search_cols = emb_vector_col_config if isinstance(emb_vector_col_config, list) else [emb_vector_col_config]
        similarity_expressions = [f'list_cosine_similarity(emb."{col}", ?)' for col in search_cols]
        similarity_clause = f"GREATEST({', '.join(similarity_expressions)})" if len(similarity_expressions) > 1 else similarity_expressions[0]
        where_not_null_clause = " AND ".join([f'emb."{col}" IS NOT NULL' for col in search_cols])

        sql_query = f"""
        SELECT {select_clause}, {similarity_clause} AS similarity
        FROM "{emb_table_name}" AS emb
        JOIN "{meta_table_name}" AS meta ON emb."{emb_id_col}" = meta."{meta_id_col}"
        WHERE {where_not_null_clause}
        """
        
        params = [query_embedding] * len(search_cols)

        if tags and meta_tags_col:
            sql_query += f' AND array_has_all(meta."{meta_tags_col}", ?)'
            params.append(tags)
        
        sql_query += " ORDER BY similarity DESC LIMIT ?"
        params.append(top_k)
        
        query_result = conn.execute(sql_query, params)
        column_names = [desc[0] for desc in query_result.description]
        return [dict(zip(column_names, row)) for row in query_result.fetchall()]

    except duckdb.Error as e:
        logger.error("duckdb_vector_search_error", extra={"error": str(e)})
        return []
    except Exception as e:
        logger.error("unknown_vector_search_error", extra={"error": str(e)})
        return []


def direct_search(
    search_config_details: Dict[str, Any],
    query_params: Dict[str, Any],
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Performs a direct search on the metadata table based on specified query parameters.
    """
    db_file = search_config_details["db_file"]
    meta_table_name = search_config_details["meta_table_name"]
    allowed_columns = search_config_details.get("direct_search_columns", [])
    all_meta_retrieval_cols = search_config_details["all_meta_retrieval_cols"]
    meta_id_col = search_config_details["meta_id_col"]

    if not query_params:
        logger.error("direct_search_empty_query_params")
        return []

    # Validate that all query keys are in the allowed direct search columns
    for key in query_params.keys():
        if key not in allowed_columns:
            logger.error("direct_search_disallowed_column", extra={"column": key, "allowed_columns": allowed_columns})
            return []

    conn = get_db_connection(db_file, read_only=True)

    try:
        # Construct the WHERE clause
        where_conditions = []
        params = []
        for key, value in query_params.items():
            where_conditions.append(f'"{key}" = ?')
            params.append(value)
        
        where_clause = " AND ".join(where_conditions)

        # Ensure all necessary columns are retrieved
        select_cols = list(dict.fromkeys([meta_id_col] + all_meta_retrieval_cols))
        select_clause = ", ".join([f'"{col}"' for col in select_cols])

        sql_query = f"""
        SELECT {select_clause}
        FROM "{meta_table_name}"
        WHERE {where_clause}
        LIMIT ?
        """
        params.append(limit)

        query_result = conn.execute(sql_query, params)
        column_names = [desc[0] for desc in query_result.description]
        return [dict(zip(column_names, row)) for row in query_result.fetchall()]

    except duckdb.Error as e:
        logger.error("duckdb_direct_search_error", extra={"error": str(e)})
        return []
    except Exception as e:
        logger.error("unknown_direct_search_error", extra={"error": str(e)})
        return []


if __name__ == "__main__":
    config_file = "search_configs/arxiv_abstract_jina_v3_api.yaml" 
    
    if not os.path.exists(config_file):
        print(f"Error: Config file '{config_file}' not found.")
    else:
        print(f"Using config file: '{config_file}'")
        search_config_details = get_search_config_details(config_file)
        if search_config_details:
            try:
                from .embedding_utils import get_embedding_provider
                model_provider = get_embedding_provider(
                    model_id=search_config_details.get("emb_model_id"),
                    model_config=search_config_details.get("model_config_params")
                )
                if model_provider:
                    example_query = "machine learning applications in healthcare"
                    search_results = search_similar_documents(
                        query_text=example_query,
                        search_config_details=search_config_details, 
                        top_k=3,
                        model_instance=model_provider
                    )
                    if search_results:
                        print(f"Found {len(search_results)} results for '{example_query}':")
                        for doc in search_results:
                            print(f"  Similarity: {doc.get('similarity', 'N/A'):.4f}, Doc: { {k: v for k, v in doc.items() if k != 'similarity'} }")
                    else:
                        print("No similar documents found.")
            except Exception as e:
                print(f"An error occurred during example execution: {e}")
        else:
            print(f"Failed to load config from '{config_file}'.")
