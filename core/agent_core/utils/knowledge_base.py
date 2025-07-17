import hashlib
import json
import uuid
import logging # Add logging module
import re
from datetime import datetime
from typing import Dict, List, Optional, Any, TypedDict, Set
import copy

# Define TypedDicts to enhance type hinting and readability

class KnowledgeItemMetadata(TypedDict, total=False):
    timestamp_added: str  # ISO 8601 format, set when item is first added
    timestamp_last_updated: str # ISO 8601 format, set on updates
    source_tool_name: str # Name of the tool that produced/retrieved this knowledge
    source_agent_id: str  # ID of the agent that invoked the tool
    tool_call_id: Optional[str] # ID of the specific LLM tool call that led to this knowledge
    contributing_tool_call_ids: List[str] # List of tool_call_ids that contributed to or updated this item
    title: Optional[str]  # e.g., webpage title, document title
    tags: Optional[List[str]] # User-defined or tool-generated tags
    original_query: Optional[str] # e.g., the search query for search results
    # New fields for dehydration/hydration tracking
    dehydration_reason: Optional[str]  # "size_threshold", "tool_policy", "explicit_request"
    original_message_role: Optional[str]  # "tool", "assistant", etc.
    access_count: int  # Number of times this item has been hydrated
    size_bytes: Optional[int]  # Size of the original content in bytes
    # ... other tool-specific or type-specific metadata

class KnowledgeItem(TypedDict):
    id: str  # Unique ID for the knowledge item (e.g., "kb_uuid")
    item_type: str  # Type of knowledge (e.g., "WEB_PAGE_CONTENT", "SEARCH_RESULT_SNIPPET", "MESSAGE_SUMMARY", "GENERIC_TOOL_OUTPUT")
    source_uri: Optional[str] # Canonical URI for the source (e.g., URL, file path, stable query string). Used for primary deduplication.
    content: Any  # The actual knowledge content (string, dict, list)
    content_hash: str  # SHA256 hash of the normalized content, for content-based deduplication.
    metadata: KnowledgeItemMetadata
    run_id: str # The run_id this knowledge item belongs to.

class KnowledgeBase:
    def __init__(self, run_id: str):
        self.run_id: str = run_id
        self.items_by_id: Dict[str, KnowledgeItem] = {} # item_id -> KnowledgeItem
        self.items_by_uri: Dict[str, str] = {}          # source_uri -> item_id
        self.items_by_hash: Dict[str, List[str]] = {}   # content_hash -> list of item_ids (content can be same for different URIs)
        self.items_by_tool_call_id: Dict[str, str] = {} # tool_call_id -> item_id (NEW INDEX)
        # KB20 Token management features
        self._next_sequence: int = 1  # Global sequence counter
        self.items_by_token: Dict[str, str] = {}  # token -> item_id mapping
        # 使用 f-string 和 run_id 的前8个字符来创建一个更具体的日志记录器名称
        self.logger = logging.getLogger(__name__) 
        self.logger.info("knowledge_base_created", extra={"description": "KnowledgeBase instance created", "run_id": run_id})

    # --- Start KB Hydration Logic ---

    def _contains_kb_refs(self, content: Any) -> bool:
        """Checks if the content (string, dict, list) contains KB token references."""
        if isinstance(content, str):
            return bool(re.search(r"<#CGKB-\d{5}>", content))
        if isinstance(content, dict):
            return any(self._contains_kb_refs(v) for v in content.values())
        if isinstance(content, list):
            return any(self._contains_kb_refs(i) for i in content)
        return False

    async def _hydrate_content_recursively(self, content: Any, seen_tokens: Set[str], max_depth: int) -> Any:
        """
        Recursively hydrates content containing knowledge base references.
        """
        if max_depth <= 0:
            return content

        if isinstance(content, str):
            # Regex to find all KB tokens
            tokens_found = re.findall(r"(<#CGKB-\d{5}>)", content)
            hydrated_content = content
            for token in tokens_found:
                if token in seen_tokens:
                    self.logger.warning("kb_circular_reference_detected", extra={"description": "Circular reference detected for token, stopping hydration for this path", "token": token})
                    continue
                
                item_id = self.items_by_token.get(token)
                if item_id and (item := self.items_by_id.get(item_id)):
                    seen_tokens.add(token) # Add before recursive call
                    # Recursively hydrate the retrieved content
                    hydrated_item_content = await self._hydrate_content_recursively(item.get("content"), seen_tokens, max_depth - 1)
                    # Convert content to string and replace
                    content_str = str(hydrated_item_content)
                    hydrated_content = hydrated_content.replace(token, content_str)
                    seen_tokens.remove(token) # Remove after recursive call
                else:
                    self.logger.warning("kb_token_not_found", extra={"description": "KB token found in content, but no corresponding item found in KnowledgeBase", "token": token})
            return hydrated_content

        if isinstance(content, dict):
            hydrated_dict = {}
            for k, v in content.items():
                hydrated_dict[k] = await self._hydrate_content_recursively(v, seen_tokens, max_depth - 1)
            return hydrated_dict

        if isinstance(content, list):
            hydrated_list = []
            for item in content:
                hydrated_list.append(await self._hydrate_content_recursively(item, seen_tokens, max_depth - 1))
            return hydrated_list

        return content

    async def hydrate_content(self, content: Any, max_depth: int = 5) -> Any:
        """
        Public hydration method for content containing KB Tokens.
        It reuses the internal recursive hydration logic.
        """
        if not self._contains_kb_refs(content):
            return content
        
        # Create a new seen_tokens set for each top-level call
        return await self._hydrate_content_recursively(content, set(), max_depth)

    async def hydrate_turn_list_tool_results(self, turns: List[Dict]) -> List[Dict]:
        """
        Iterates through a list of Turns and hydrates the result_payload in all tool_interactions.
        Returns a new, hydrated list of Turns.
        """
        hydrated_turns = copy.deepcopy(turns)
    
        for turn in hydrated_turns:
            for interaction in turn.get("tool_interactions", []):
                payload_to_hydrate = interaction.get("result_payload")
                if payload_to_hydrate:
                    hydrated_payload = await self.hydrate_content(payload_to_hydrate)
                    interaction["result_payload"] = hydrated_payload
        
        return hydrated_turns

    # --- End KB Hydration Logic ---

    def _calculate_content_hash(self, content: Any) -> str:
        if isinstance(content, (dict, list)):
            try:
                # Remove unnecessary spaces to ensure consistent hashes
                serialized_content = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
            except TypeError as e:
                self.logger.warning("kb_content_serialization_failed", extra={"description": "Cannot JSON serialize content for hashing, falling back to str()", "error": str(e), "content_type": str(type(content)), "content_preview": str(content)[:100]})
                serialized_content = str(content) # Fallback
        else:
            serialized_content = str(content)
        return hashlib.sha256(serialized_content.encode('utf-8')).hexdigest()

    async def add_item(self, item_data: Dict) -> Dict[str, Any]:
        item_type = item_data.get("item_type")
        content = item_data.get("content")

        # More detailed logging
        self.logger.debug("kb_add_item_received", extra={"description": "KB add_item: Received item", "item_type": item_type, "item_type_type": str(type(item_type)), "content_preview": str(content)[:100], "content_type": str(type(content))})
        
        if item_type is None or content is None: # The original check
            msg = "item_type and content are required to add an item to KnowledgeBase."
            # Log the actual values that failed the check
            self.logger.error("kb_add_item_validation_error", extra={"description": msg, "item_data_keys": list(item_data.keys()), "item_type": item_type, "content_is_none": content is None})
            return {"status": "error", "message": msg, "item_id": None}

        source_uri = item_data.get("source_uri")
        provided_metadata = item_data.get("metadata", {}) 
        
        current_tool_call_id = provided_metadata.get("tool_call_id")
        
        content_hash = self._calculate_content_hash(content)

        # 1. Check by source_uri (if provided)
        if source_uri:
            existing_item_id_by_uri = self.items_by_uri.get(source_uri)
            if existing_item_id_by_uri and existing_item_id_by_uri in self.items_by_id:
                existing_item = self.items_by_id[existing_item_id_by_uri]
                if existing_item["content_hash"] == content_hash:
                    self.logger.debug("kb_uri_hash_match_deduplicated", extra={"description": "Item with URI and same content hash already exists. Merging metadata", "source_uri": source_uri, "content_hash_preview": content_hash[:8], "item_id": existing_item_id_by_uri})
                    if current_tool_call_id and current_tool_call_id not in existing_item["metadata"].get("contributing_tool_call_ids", []):
                        existing_item["metadata"].setdefault("contributing_tool_call_ids", []).append(current_tool_call_id)
                        existing_item["metadata"]["timestamp_last_updated"] = datetime.now().isoformat()
                    
                    # KB20: Ensure the existing item has a token
                    if "token" not in existing_item["metadata"]:
                        token = self.generate_next_token()
                        existing_item["metadata"]["token"] = token
                        self.items_by_token[token] = existing_item_id_by_uri
                    else:
                        token = existing_item["metadata"]["token"]
                    
                    return {"status": "success_deduplicated_uri_hash_match", "item_id": existing_item_id_by_uri, "token": token, "message": "Item already exists with same URI and content."}
                else:
                    self.logger.info("kb_uri_match_content_update", extra={"description": "Item with URI exists but content hash differs. Updating item", "source_uri": source_uri, "item_id": existing_item_id_by_uri})
                    old_hash = existing_item["content_hash"]
                    
                    existing_item["content"] = content
                    existing_item["content_hash"] = content_hash
                    existing_item["item_type"] = item_type 
                    
                    new_meta = {**existing_item["metadata"], **provided_metadata} 
                    existing_item["metadata"] = new_meta # type: ignore
                    existing_item["metadata"]["timestamp_last_updated"] = datetime.now().isoformat()
                    if current_tool_call_id:
                         existing_item["metadata"].setdefault("contributing_tool_call_ids", []).append(current_tool_call_id)
                         existing_item["metadata"]["contributing_tool_call_ids"] = sorted(list(set(existing_item["metadata"]["contributing_tool_call_ids"])))

                    if self.items_by_hash.get(old_hash) and existing_item_id_by_uri in self.items_by_hash[old_hash]:
                        self.items_by_hash[old_hash].remove(existing_item_id_by_uri)
                        if not self.items_by_hash[old_hash]:
                            del self.items_by_hash[old_hash]
                    self.items_by_hash.setdefault(content_hash, []).append(existing_item_id_by_uri)
                    
                    # KB20: Ensure the updated item has a token
                    if "token" not in existing_item["metadata"]:
                        token = self.generate_next_token()
                        existing_item["metadata"]["token"] = token
                        self.items_by_token[token] = existing_item_id_by_uri
                    else:
                        token = existing_item["metadata"]["token"]
                    
                    return {"status": "success_updated_uri_match", "item_id": existing_item_id_by_uri, "token": token, "message": "Item updated with new content for existing URI."}

        # 2. Check by content_hash
        existing_item_ids_with_same_hash = self.items_by_hash.get(content_hash, [])
        if existing_item_ids_with_same_hash:
            for existing_id in existing_item_ids_with_same_hash:
                if existing_id in self.items_by_id:
                    existing_item_for_hash_match = self.items_by_id[existing_id]
                    if source_uri and (not existing_item_for_hash_match.get("source_uri") or self.items_by_uri.get(source_uri) != existing_id) :
                        self.logger.info("kb_hash_match_new_uri", extra={"description": "Found existing content with hash, associating new URI", "content_hash_preview": content_hash[:8], "source_uri": source_uri})
                        existing_item_for_hash_match["source_uri"] = source_uri
                        self.items_by_uri[source_uri] = existing_id
                        
                        if current_tool_call_id and current_tool_call_id not in existing_item_for_hash_match["metadata"].get("contributing_tool_call_ids", []):
                            existing_item_for_hash_match["metadata"].setdefault("contributing_tool_call_ids", []).append(current_tool_call_id)
                            existing_item_for_hash_match["metadata"]["timestamp_last_updated"] = datetime.now().isoformat()
                        
                        # KB20: Ensure the hash-matched item has a token
                        if "token" not in existing_item_for_hash_match["metadata"]:
                            token = self.generate_next_token()
                            existing_item_for_hash_match["metadata"]["token"] = token
                            self.items_by_token[token] = existing_id
                        else:
                            token = existing_item_for_hash_match["metadata"]["token"]
                        
                        return {"status": "success_enriched_hash_match_with_uri", "item_id": existing_id, "token": token, "message": "Content matched existing item; new URI associated."}
                    
                    elif not source_uri:
                        self.logger.debug("kb_hash_match_no_uri_deduplicated", extra={"description": "Item with content hash (no URI) already exists. Ignoring new", "content_hash_preview": content_hash[:8], "item_id": existing_id})
                        if current_tool_call_id and current_tool_call_id not in existing_item_for_hash_match["metadata"].get("contributing_tool_call_ids", []):
                             existing_item_for_hash_match["metadata"].setdefault("contributing_tool_call_ids", []).append(current_tool_call_id)
                             existing_item_for_hash_match["metadata"]["timestamp_last_updated"] = datetime.now().isoformat()
                        
                        # KB20: Ensure the hash-matched (no URI) item has a token
                        if "token" not in existing_item_for_hash_match["metadata"]:
                            token = self.generate_next_token()
                            existing_item_for_hash_match["metadata"]["token"] = token
                            self.items_by_token[token] = existing_id
                        else:
                            token = existing_item_for_hash_match["metadata"]["token"]
                        
                        return {"status": "success_deduplicated_hash_match_no_uri", "item_id": existing_id, "token": token, "message": "Item with same content (no URI) already exists."}

        # 3. Add as new item
        new_item_id = item_data.get("id", f"kb_{uuid.uuid4().hex}")
        # KB20: Generate a token for the new item
        token = self.generate_next_token()
        
        final_new_metadata: KnowledgeItemMetadata = { # type: ignore
            "timestamp_added": datetime.now().isoformat(),
            "timestamp_last_updated": datetime.now().isoformat(),
            "contributing_tool_call_ids": [current_tool_call_id] if current_tool_call_id else [],
            "token": token  # KB20: Store the token in metadata
        }
        final_new_metadata.update(provided_metadata) # type: ignore

        new_knowledge_item: KnowledgeItem = {
            "id": new_item_id,
            "item_type": item_type, # type: ignore
            "source_uri": source_uri,
            "content": content,
            "content_hash": content_hash,
            "metadata": final_new_metadata,
            "run_id": item_data.get("run_id") # type: ignore
        }

        self.items_by_id[new_item_id] = new_knowledge_item
        # KB20: Establish token mapping
        self.items_by_token[token] = new_item_id
        
        if source_uri:
            self.items_by_uri[source_uri] = new_item_id
        
        # Add tool_call_id index
        if current_tool_call_id:
            self.items_by_tool_call_id[current_tool_call_id] = new_item_id
        
        self.items_by_hash.setdefault(content_hash, []).append(new_item_id)
        self.items_by_hash[content_hash] = sorted(list(set(self.items_by_hash[content_hash])))

        self.logger.info("kb_item_added", extra={"description": "Added new item to knowledge base", "item_id": new_item_id, "token": token, "item_type": item_type, "source_uri": source_uri, "content_hash_preview": content_hash[:8]})
        return {"status": "success_new_item_added", "item_id": new_item_id, "token": token, "message": "New knowledge item added."}

    def generate_next_token(self) -> str:
        """Generates the next available token."""
        token = f"<#CGKB-{self._next_sequence:05d}>"
        self._next_sequence += 1
        return token

    async def store_with_token(self, content: Any, metadata: Dict) -> str:
        """Stores content and returns a token."""
        import uuid
        item_id = f"kb_{uuid.uuid4().hex}"
        token = self.generate_next_token()

        # Extend metadata to include token-related information
        extended_metadata = {
            **metadata,
            "token": token,
            "timestamp_added": datetime.now().isoformat(),
            "timestamp_last_updated": datetime.now().isoformat(),
        }

        kb_item: KnowledgeItem = {
            "id": item_id,
            "item_type": metadata.get("item_type", "TOKEN_DEHYDRATED_CONTENT"),
            "source_uri": None,
            "content": content,
            "content_hash": self._calculate_content_hash(content),
            "metadata": extended_metadata, # type: ignore
            "run_id": self.run_id
        }

        self.items_by_id[item_id] = kb_item
        self.items_by_token[token] = item_id
        
        # Add to content_hash index
        content_hash = kb_item["content_hash"]
        self.items_by_hash.setdefault(content_hash, []).append(item_id)
        
        self.logger.info("kb_content_stored_with_token", extra={"description": "Stored content with token", "token": token, "item_id": item_id})
        return token

    async def get_item_by_uri(self, source_uri: str) -> Optional[KnowledgeItem]:
        item_id = self.items_by_uri.get(source_uri)
        if item_id:
            return self.items_by_id.get(item_id)
        return None

    async def has_item_with_uri(self, source_uri: str) -> bool:
        return source_uri in self.items_by_uri

    async def find_items(self, query_params: Dict) -> List[KnowledgeItem]:
        self.logger.warning("kb_find_items_not_implemented", extra={"description": "KnowledgeBase.find_items() is not fully implemented yet. Returning empty list"})
        # TODO: Implement basic filtering based on item_type, tags in metadata, etc.
        # Example basic filtering (can be expanded):
        # results = []
        # for item in self.items_by_id.values():
        #     match = True
        #     if "item_type" in query_params and item.get("item_type") != query_params["item_type"]:
        #         match = False
        #     if "tags" in query_params and not set(query_params["tags"]).issubset(set(item.get("metadata", {}).get("tags", []))):
        #         match = False
        #     # Add more query_params checks here
        #     if match:
        #         results.append(item)
        # return results
        return []
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize the KnowledgeBase state to a dictionary."""
        return {
            "run_id": self.run_id,
            "items_by_id": self.items_by_id,
            "items_by_uri": self.items_by_uri,
            "items_by_hash": self.items_by_hash,
            "items_by_tool_call_id": self.items_by_tool_call_id,
            "_next_sequence": self._next_sequence,
            "items_by_token": self.items_by_token,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KnowledgeBase':
        """Deserialize a KnowledgeBase from a dictionary."""
        run_id = data.get("run_id", "deserialized_run")
        kb = cls(run_id)
        kb.items_by_id = data.get("items_by_id", {})
        kb.items_by_uri = data.get("items_by_uri", {})
        kb.items_by_hash = data.get("items_by_hash", {})
        kb.items_by_tool_call_id = data.get("items_by_tool_call_id", {})
        kb._next_sequence = data.get("_next_sequence", 1)
        kb.items_by_token = data.get("items_by_token", {})
        kb.logger.info("kb_restored_from_dict", extra={"description": "KnowledgeBase restored from dictionary", "run_id": run_id, "item_count": len(kb.items_by_id)})
        return kb
    
    def get_items_batch(self, item_ids: List[str]) -> Dict[str, Optional[KnowledgeItem]]:
        """Batch get multiple KB items for performance optimization."""
        result = {}
        for item_id in item_ids:
            result[item_id] = self.items_by_id.get(item_id)
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """Get KB statistics for monitoring."""
        total_size = sum(len(str(item.get("content", ""))) for item in self.items_by_id.values())
        return {
            "total_items": len(self.items_by_id),
            "total_size_bytes": total_size,
            "items_by_type": self._count_by_type(),
            "average_size": total_size // len(self.items_by_id) if self.items_by_id else 0,
            "total_accesses": sum(item.get("metadata", {}).get("access_count", 0) for item in self.items_by_id.values())
        }
    
    def _count_by_type(self) -> Dict[str, int]:
        """Count items by type for statistics."""
        type_counts = {}
        for item in self.items_by_id.values():
            item_type = item.get("item_type", "unknown")
            type_counts[item_type] = type_counts.get(item_type, 0) + 1
        return type_counts
