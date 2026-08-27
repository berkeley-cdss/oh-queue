# LLM Tips Render Box Configuration Spec

## Scope
This spec describes how the UI box that renders LLM response text (`LlmTips`) is enabled, populated, and styled.

## Component Contract
- Component: `oh_queue/static/js/components/llm_tips.js`
- Props:
  - `tips: string` (required to render; falsy values return `null`)
  - `className: string` (optional variant class)
- Rendering:
  - Root classes: `"ticket-llm-tips"` plus `className`
  - Title text is fixed: `LLM Tips`
  - Body is rendered with `ReactMarkdown` from the `tips` string

## Data Source
- Persistent field: `ticket.llm_tips` (`Text`) in `oh_queue/models.py`
- Serialization to client state: `ticket_json(...)["llm_tips"]` in `oh_queue/views.py`

## Feature Gating (When Box Can Appear)
The box is only shown for staff users, and only when all conditions pass:
1. `enable_llm_features` config is true
2. `ticket.llm_tips` is present/non-empty
3. Current view has LLM tips render logic

### Queue List (Inline Box)
- File: `oh_queue/static/js/components/ticket.js`
- Condition: `staff && llmTipsEnabled && ticket.llm_tips`
- Variant class: `ticket-llm-tips--inline`

### Ticket Detail Page (Card Box)
- File: `oh_queue/static/js/components/ticket_layout.js`
- Condition: `isStaff(state) && enable_llm_features && ticket.llm_tips`
- Variant class: `ticket-llm-tips--card`

## How `enable_llm_features` Is Configured
- Admin toggle location:
  - `oh_queue/static/js/components/admin_tickets_manager.js`
  - Uses `ConfigLinkedToggle` for `configKey="enable_llm_features"`
- Backend default:
  - Created as `"false"` in `init_config` (`oh_queue/views.py`)
  - Ensured to exist by `ensure_config_entry("enable_llm_features", "false", True)` in index bootstrap (`oh_queue/views.py`)
- Client parsing:
  - Parsed from string to boolean in `oh_queue/static/js/components/app.js`

## How `ticket.llm_tips` Gets Populated
- Ticket submission stores `use_llm` opt-in.
- Backend calls `request_llm_tips_if_enabled(ticket)` after ticket creation.
- If feature is enabled, ticket opted-in, and endpoint/token are configured:
  - POST payload is sent to `LLM_TIPS_ENDPOINT` with `Authorization` header from `LLM_TIPS_AUTH_TOKEN`
  - Response text is read from first present key in: `llm_tips`, `tips`, `Miloh`
  - `ticket.llm_tips` is saved and a ticket `update` event is emitted
- If call fails, times out, or has invalid/missing response text, `ticket.llm_tips` remains unset and box does not render.

## Styling Configuration
- Base style: `.ticket-llm-tips` in `oh_queue/static/css/style.css`
  - Border, light blue background, rounded corners, compact typography
- Title style: `.ticket-llm-tips-title`
  - Uppercase label styling and spacing
- Body style: `.ticket-llm-tips-body`
- Inline variant: `.ticket-llm-tips--inline`
  - Full-width block in list rows
  - Uses 3-line clamp via `-webkit-line-clamp: 3`
- Card variant: `.ticket-llm-tips--card`
  - Vertical spacing for ticket detail page

## Runtime Dependencies
- `enable_llm_features` config entry available in course config state
- Ticket JSON includes `llm_tips`
- Frontend bundle includes `ReactMarkdown` and `classNames`
- Backend has valid LLM endpoint/auth config when generating tips

## Non-Goals
- This spec does not define LLM prompt engineering or provider internals.
- This spec does not define moderation/sanitization policy beyond current markdown rendering behavior.
