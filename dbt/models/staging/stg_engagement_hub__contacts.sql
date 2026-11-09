select
    contact_id,
    entity_id,
    full_name,
    email,
    lower(trim(email))                    as email_normalised,
    cast(task_count as integer)           as task_count,
    cast(conversation_count as integer)   as conversation_count
from {{ source('raw', 'engagement_hub_contacts') }}
