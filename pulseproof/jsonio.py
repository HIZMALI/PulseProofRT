"""Reject ambiguous JSON rather than silently accepting duplicate keys or NaN."""
import json

def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result

def _constant(value):
    raise ValueError(f"Non-finite JSON number: {value}")

def loads(text):
    return json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
