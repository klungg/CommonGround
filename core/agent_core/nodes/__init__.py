# Try to import custom nodes, ignore if the file or class does not exist
try:
    from .custom_nodes.stage_planner_node import StagePlannerNode
except ImportError:
    StagePlannerNode = None # type: ignore
try:
    from .custom_nodes.dispatcher_node import DispatcherNode
except ImportError:
    DispatcherNode = None # type: ignore
try:
    from .custom_nodes.finish_node import FinishNode
except ImportError:
    FinishNode = None # type: ignore


_all_nodes = [
    'AgentNode',
    'StagePlannerNode', # Assuming this is a custom tool node to keep
    'DispatcherNode',   # Custom tool node to keep
    'FinishNode'        # Custom tool node to keep

    # Old specific agent nodes like PrincipalNode, AssociateNode, etc., are removed.
    # Service nodes like ChatCompletionNode, FIMNode are replaced by AgentNode with specific profiles.
    # Utility nodes like MarkdownReportGeneratorNode, MessageSummaryNode are replaced by AgentNode with specific profiles.

]

# Filter out None values in case of import errors
# Ensure that only the explicitly listed and successfully imported nodes are in __all__
_final_exports = []
for node_name_str in _all_nodes:
    if node_name_str in globals() and globals()[node_name_str] is not None:
        _final_exports.append(node_name_str)
    elif node_name_str == 'AgentNode': # AgentNode is fundamental
        _final_exports.append('AgentNode')


__all__ = _final_exports
