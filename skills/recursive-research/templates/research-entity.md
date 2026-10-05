# Enumerate every {{TYPE_NAME}}

You are researching **{{SUBJECT}}**. Produce the complete list of every
{{TYPE_NAME}}, with exact values for every property.

**Web search is required.** Search before you write anything. If the search
tools are missing or fail, write nothing and reply with the single line
`SEARCH_UNAVAILABLE: <what failed>`. Do not list instances from memory.

## Schema

{{TYPE_SCHEMA}}

`{{WORKSPACE}}/knowledge/spec.md` has background. It is a starting point, not
a complete list; find the instances it does not mention.

## Write

Write JSON to `{{WORKSPACE}}/{{OUTPUT}}` in exactly this shape:

    {
      "entity_type": "{{TYPE_NAME}}",
      "count": 2,
      "_meta": {"last_updated": "YYYY-MM-DD", "sources": ["..."]},
      "entities": [
        {
          "name": "Instance name",
          "properties": {"<property>": <value>, "<property>": null},
          "provenance": {"<property>": "PRIMARY", "<property>": "UNKNOWN"},
          "notes": null
        }
      ]
    }

- Every entity has every property in the schema, and no others.
- A value you could not find is `null`, and its tier is `UNKNOWN`.
- Numbers are numbers, not strings.
- `provenance` gives a tier for every property. If every property of an
  entity came from the same source, it may be a single tier string.
- `count` equals the number of entities.
- `notes` is one sentence or `null`. Use it to say which version a value
  belongs to when versions differ.

## Provenance

Tiers, strongest first: `PRIMARY`, `EXPERT`, `SECONDARY`, `INFERRED`,
`OBSERVED`, `UNKNOWN`. For this subject:

{{PROVENANCE_MAPPING}}

Completeness matters, but not more than accuracy. A `null` is correct when
you do not know. An invented value is a defect.
