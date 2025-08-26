# FastMCP Lark Server - Production Ready

🚀 **Production-Ready Async MCP Server** for Lark/Feishu Integration

## Features

✅ **7 Advanced Async MCP Tools** - All tested and validated  
✅ **Token caching & management** - Optimized performance  
✅ **Comprehensive error handling** - Production-grade reliability  
✅ **Zero-risk deployment strategy** - Current system fully protected  
✅ **Complete deployment instructions** - Ready to upload and deploy  

## MCP Tools Available

1. **send_message** - Send messages to Lark chats or users
2. **get_chat_list** - Get list of chats the bot has access to
3. **get_chat_members** - Get members of a specific chat
4. **create_calendar_event** - Create calendar events in Lark
5. **upload_file** - Upload files to Lark
6. **get_user_info** - Get information about specific users
7. **create_doc** - Create new documents in Lark Docs

## Quick Start

### Environment Variables

Set the following environment variables:

```bash
LARK_APP_ID=your_app_id_here
LARK_APP_SECRET=your_app_secret_here
```

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python fastmcp_async_lark.py
```

### Production Deployment

#### Deploy on Render

1. Fork this repository
2. Connect to Render using the `render.yaml` configuration
3. Set environment variables in Render dashboard
4. Deploy!

The server will be available at your Render URL.

## API Architecture

- **Async/Await** - Full async support for optimal performance
- **Token Caching** - Automatic token refresh with caching
- **Error Handling** - Comprehensive error handling and logging
- **HTTP Client** - Persistent HTTP client with connection pooling

## Security Features

- Environment variable configuration
- Token expiration handling
- Request timeout management
- Comprehensive logging

## Zero-Risk Deployment

This server uses the **MCP protocol** which is completely isolated from your existing **REST API** system. This means:

- ✅ No interference with current webhook system
- ✅ Parallel deployment capability
- ✅ Instant rollback if needed
- ✅ Protocol isolation guarantees safety

## Current System Protection

Your existing system `<your-current-system-id>` remains:
- ✅ **PROTECTED** - No changes to existing system
- ✅ **OPERATIONAL** - Continues to work normally
- ✅ **ROLLBACK READY** - Instant switch back capability

## Support

For issues or questions, please open an issue in this repository.

---

**Ready for Production Deployment! 🚀**