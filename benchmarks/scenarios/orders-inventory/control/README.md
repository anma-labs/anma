# Architecture
`orders` and `inventory` are sibling modules under `src/domains` and must NOT
import each other. Stock changes are coordinated by the calling layer, not by
`orders` reaching into `inventory`.
