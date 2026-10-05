# Enumerate every {{TYPE_NAME}}

You are researching **{{SUBJECT}}**. Produce the complete list of every
{{TYPE_NAME}}, with exact values for every property.

**Web search is required.** Search before you write anything. If the search
tools are missing or fail, write nothing and reply with the single line
`SEARCH_UNAVAILABLE: <what failed>`. Do not list instances from memory.

## Schema

{{TYPE_SCHEMA}}

`{{WORKSPACE}}/knowledge/spec.md` has background. Do not read the whole file:
search it for this type's name and its example instances, and read only those
passages. It is a starting point, not a complete list; find the instances it
does not mention.

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

**How you read a source limits its tier.** The web tools return a summary
written by a model, not the page's own text. A claim you learned only through
a web fetch or a search result is at most `SECONDARY`, even when the page is
the specification itself. `PRIMARY` is only for text you read directly: a
local file you opened, or a passage you can copy word for word from what the
tool returned. When you are not sure the words are the source's own, use the
lower tier.

If a value is `PRIMARY`, say in `notes` where its exact words can be found.

Completeness matters, but not more than accuracy. A `null` is correct when
you do not know. An invented value is a defect.
