#  tools/list returns: 
TOOLS = {
    "chart_detector": {
        "name": "chart_detector",
        "title": "Chart Detector",
        "description": "Determine if a user question is chartable, suggest chart type, and produce a safe SELECT SQL template.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "schema_text": {"type": "string"}
            },
            "required": ["question"]
        }
    },
    "chart_renderer": {
        "name": "chart_renderer",
        "title": "Chart Renderer",
        "description": "Execute a safe SELECT SQL and render a chart image (png). Returns image URL and basic stats.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string"},
                "plot_type": {"type": "string"},
                "limit_rows": {"type": "integer"}
            },
            "required": ["sql", "plot_type"]
        }
    }
}
