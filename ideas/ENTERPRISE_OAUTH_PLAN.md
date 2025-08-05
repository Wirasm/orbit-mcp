# 🔐 **Enterprise OAuth & User Management Plan for Orbit MCP**

## **🔍 Current State Analysis**

### **Docker MCP OAuth Reality Check**
- **Limited OAuth Support**: Only `github` and `gdrive` have built-in OAuth
- **Most Services Use Manual Tokens**: Notion (Internal Integration Token), Slack (Bot Token), Resend (API Key)
- **No User Management**: Current system is single-user focused
- **Manual Secret Management**: Requires `docker secret create` commands

### **Industry Standards & Problems**

**MCP OAuth Specification Issues** (Based on Expert Analysis):
1. **Architectural Problem**: MCP spec makes servers both authorization + resource servers
2. **Scalability Issues**: Stateful token management makes scaling difficult
3. **Security Concerns**: Servers must maintain secure token databases
4. **Enterprise Incompatibility**: Doesn't integrate with existing Identity Providers

## **🏗️ Proposed Enterprise Architecture**

### **Option 1: OAuth Proxy Gateway (Recommended)**

**Architecture**:
```
Company Admin → Orbit OAuth Gateway → Individual Service OAuth → MCP Servers
     ↓                    ↓                      ↓
User Invitation → User OAuth Flow → Service Tokens → Per-User Tool Access
```

**Components**:
1. **Orbit OAuth Gateway**
   - Central OAuth coordinator
   - Handles user invitation flows
   - Manages per-user service tokens
   - Integrates with company SSO/IdP

2. **Service-Specific OAuth Handlers**
   - Notion: Use Notion's public integration OAuth
   - Slack: Slack App OAuth with workspace permissions
   - Google: Google Workspace OAuth for Drive/Gmail

3. **User Management Database**
   - User profiles and company associations
   - Per-user service token storage (encrypted)
   - Pack assignments and permissions
   - Audit logs

### **Option 2: Enterprise IdP Integration**

**Architecture**:
```
Company SSO/SAML → Orbit MCP → Service-Specific Token Exchange → Tools
```

**Benefits**:
- Leverages existing company authentication
- Single sign-on experience
- Centralized user management
- Compliance with enterprise security policies

## **🎯 Proposed User Experience**

### **Company Admin Flow**
```bash
# 1. Company setup
setup_company("widinglabs", "admin@widinglabs.com")

# 2. Configure service integrations (one-time)
configure_oauth("notion", workspace_id="widinglabs-workspace")
configure_oauth("slack", workspace_id="T1234567")
configure_oauth("resend", domain="widinglabs.com")

# 3. Invite users and assign packs
invite_user("rasmus@widinglabs.com", packs=["widinglabs"])
assign_pack("user@company.com", "frontend-stack")
```

### **User Flow**
```bash
# 1. User receives invitation email
# 2. Clicks OAuth authorization links
# 3. Grants permissions to Orbit for each service
# 4. Tools become immediately available

# Simple usage
list_my_tools()  # Shows tools from assigned packs
use_notion_tool("create_page", {...})  # Works with user's OAuth tokens
```

## **🛠️ Technical Implementation Strategy**

### **Phase 1: OAuth Gateway Foundation**
1. **Service OAuth Research**
   - Notion: Use public integration OAuth (supports workspace-wide access)
   - Slack: Create Slack App with OAuth 2.0 flow
   - Google Workspace: Use Google OAuth for Drive/Gmail APIs
   - Resend: Implement domain-based authorization

2. **Database Schema**
   ```sql
   -- Companies
   companies (id, name, domain, settings)
   
   -- Users
   users (id, email, company_id, role, status)
   
   -- Service Tokens (encrypted)
   user_tokens (user_id, service, token_data, expires_at)
   
   -- Pack Assignments
   user_packs (user_id, pack_name, assigned_by, assigned_at)
   ```

### **Phase 2: Integration Layer**
1. **OAuth Coordinator Service**
   - Handle OAuth flows for each service
   - Token refresh and management
   - Per-user token isolation

2. **MCP Server Proxy**
   - Intercept MCP server calls
   - Inject appropriate user tokens
   - Route to correct user-specific instances

### **Phase 3: Admin Dashboard**
1. **Company Management UI**
   - User invitation and management
   - Pack assignment interface
   - Usage analytics and audit logs
   - Service integration status

## **🚀 Implementation Roadmap**

### **Immediate Next Steps** (Don't Implement Yet)
1. **Research Service OAuth APIs**:
   - Notion Public Integration OAuth flow
   - Slack App OAuth with granular permissions
   - Google Workspace API OAuth scopes
   - Resend domain verification and API access

2. **Design User Database Schema**:
   - Multi-tenant architecture
   - Encrypted token storage
   - Role-based access control
   - Audit trail requirements

3. **OAuth Flow Prototyping**:
   - Build minimal OAuth coordinator
   - Test with one service (Notion recommended)
   - Validate token refresh patterns
   - Test multi-user isolation

### **Enterprise Requirements to Address**
- **Security**: Encrypted token storage, HTTPS everywhere, token rotation
- **Compliance**: Audit logs, data retention policies, GDPR compliance
- **Scalability**: Stateless MCP servers, horizontal scaling capability
- **Integration**: SSO/SAML support, existing IdP integration
- **Management**: Admin dashboards, user self-service, usage analytics

## **💡 Key Insights**

1. **Current MCP OAuth Spec is Insufficient** for enterprise use
2. **Most Popular Services Don't Use MCP OAuth** (Notion, Slack, Resend use proprietary auth)
3. **Enterprise Needs Centralized User Management** with per-user tool access
4. **OAuth Proxy Pattern** is the most practical approach
5. **Service-by-Service OAuth Integration** is required (no universal solution)

## **🔄 Current Authentication Reality**

### **Widinglabs Pack Authentication Requirements**

Based on Docker MCP Gateway logs analysis:

1. **Notion Server** 
   - **Server**: `notion` (Official Notion MCP Server)
   - **Tools**: 19 tools available
   - **Authentication Required**: 
     - `INTERNAL_INTEGRATION_TOKEN` (Notion Integration Token)
     - `OPENAPI_MCP_HEADERS` (optional headers)

2. **Slack Server**
   - **Server**: `slack` (Interact with Slack Workspaces over the Slack API)
   - **Authentication Required**:
     - `SLACK_BOT_TOKEN` (Slack Bot Token) 
     - `SLACK_TEAM_ID` (Your Slack Team/Workspace ID)
     - `SLACK_CHANNEL_IDS` (Channel IDs to access)

3. **Resend Email Server**
   - **Server**: `resend` (Send emails directly from Cursor)
   - **Authentication Required**:
     - `RESEND_API_KEY` (Resend API Key)
     - `SENDER_EMAIL_ADDRESS` (Your verified sender email)
     - `REPLY_TO_EMAIL_ADDRESSES` (Reply-to addresses)

## **🎯 Transformation Vision**

This would transform Orbit MCP from a personal tool manager into a **true enterprise MCP orchestration platform** with:

- **Proper User Management**: Multi-tenant, role-based access
- **OAuth Flows**: Service-specific authentication handled centrally
- **Company Admin Controls**: Invitation, pack assignment, usage monitoring
- **Enterprise Security**: Encrypted tokens, audit trails, compliance features
- **Scalable Architecture**: Stateless servers, horizontal scaling capability

**Next decision point**: Which service should we prototype the OAuth flow with first? Notion is probably the best candidate due to their public integration OAuth support.

---

**Document Status**: Research Complete - Ready for Implementation Planning  
**Last Updated**: 2025-08-04  
**Priority**: High - Critical for enterprise adoption