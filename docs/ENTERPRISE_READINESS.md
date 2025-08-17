Enterprise Pack (Phase 45)

Features
- SSO configuration endpoints: OIDC or SAML; deterministic validator
- RBAC: roles viewer, editor, admin with scoped permissions
- Audit export: JSON or CSV covering privileged actions

API
- POST /auth/sso/config { tenant_id, protocol: oidc|saml, config: {...} }
- GET /audit/export?tenant_id=...&fmt=json|csv

Headers
- X-Role: viewer|editor|admin

SSO Config Validation
- oidc requires: issuer, client_id, client_secret
- saml requires: idp_entity_id, sso_url, certificate


