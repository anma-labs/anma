# shop (TypeScript)

Architecture note: `billing` may import `accounts`. `accounts` must **not**
import `billing` — keep accounts decoupled; invoiced totals are injected by the
caller. (This is the only signal in the control arm; nothing enforces it.)
