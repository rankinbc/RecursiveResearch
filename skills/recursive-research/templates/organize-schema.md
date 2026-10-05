# Identify the entity types of {{SUBJECT}}

Read `{{WORKSPACE}}/knowledge/spec.md` and write
`{{WORKSPACE}}/knowledge/entities.json`.

This is a schema pass. Identify the kinds of thing that exist and what
properties they have. A later stage lists every instance.

## What counts as an entity type

A category with several named instances that share comparable properties.
Tables in the survey almost always indicate one.

Not an entity type: something there is only one of, an abstract principle, or
a fact about the subject as a whole.

The plan expected these types: {{EXPECTED_TYPES}}. Treat that as a starting
list. Add types the survey reveals, and leave out expected types the survey
shows do not exist.

## Write

    {
      "entity_types": [
        {
          "name": "MessageType",
          "description": "One sentence on what this is",
          "estimated_count": 12,
          "examples": ["HELLO", "PING"],
          "properties": [
            {"name": "code", "type": "number", "unit": null, "description": "brief"}
          ]
        }
      ],
      "relationships": [
        {"type": "replies_to", "from_type": "MessageType", "to_type": "MessageType",
         "description": "How the types relate"}
      ]
    }

- Names in PascalCase, using the subject's own terms.
- Two or three examples per type, only to confirm the type exists.
- Property names in snake_case. Include every property a complete record of
  one instance would need, even where the survey has no values yet.
- `type` is `number`, `string`, `boolean`, or `array`.
- Be thorough about types. A type missed here is never enumerated.
