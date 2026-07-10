REGULATION_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string"
        },
        "organization": {
            "type": "string"
        },
        "publish_date": {
            "type": "string"
        },
        "effective_date": {
            "type": "string"
        },
        "countries": {
            "type": "array",
            "items": {
                "type": "string"
            }
        },
        "products": {
            "type": "array",
            "items": {
                "type": "string"
            }
        },
        "importance": {
            "type": "string"
        },
        "summary": {
            "type": "string"
        }
    },
    "required": [
        "title",
        "organization",
        "publish_date",
        "effective_date",
        "countries",
        "products",
        "importance",
        "summary"
    ],
    "additionalProperties": False
}