#!/usr/bin/env python3
"""
Combined FastAPI + FastMCP Server for Render Deployment
Provides HTTP health endpoints AND FastMCP WebSocket functionality
"""

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

import httpx
import uvicorn
from fastapi import FastAPI, WebSocket
from fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global HTTP client and token cache
http_client: Optional[httpx.AsyncClient] = None
token_cache = {
    'access_token': None,
    'expires_at': None,
    'tenant_access_token': None,
    'tenant_expires_at': None
}

# Initialize FastAPI app
app = FastAPI(title="FastMCP Lark Server", version="1.0.0")

# Initialize MCP server
mcp = FastMCP("Lark Server")

# Initialize token manager
token_manager = None

class LarkTokenManager:
    """Manages Lark API tokens with caching and automatic refresh"""
    
    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = "https://open.feishu.cn/open-apis"
    
    async def get_tenant_access_token(self) -> str:
        """Get tenant access token with caching"""
        global token_cache
        
        # Check if cached token is still valid
        if (token_cache['tenant_access_token'] and 
            token_cache['tenant_expires_at'] and 
            time.time() < token_cache['tenant_expires_at']):
            return token_cache['tenant_access_token']
        
        # Refresh token
        url = f"{self.base_url}/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        
        try:
            response = await http_client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') == 0:
                token_cache['tenant_access_token'] = data['tenant_access_token']
                token_cache['tenant_expires_at'] = time.time() + data['expire'] - 300  # 5min buffer
                logger.info("Tenant access token refreshed successfully")
                return token_cache['tenant_access_token']
            else:
                raise Exception(f"Token refresh failed: {data}")
                
        except Exception as e:
            logger.error(f"Failed to refresh tenant access token: {e}")
            raise

# FastAPI HTTP Endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "FastMCP Lark Server",
        "status": "running",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "mcp_websocket": "/ws"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for Render monitoring"""
    try:
        # Check if token manager is initialized
        manager_status = "initialized" if token_manager else "not_initialized"
        
        # Check environment variables (without exposing values)
        env_check = {
            "lark_app_id_set": bool(os.getenv('LARK_APP_ID')),
            "lark_app_secret_set": bool(os.getenv('LARK_APP_SECRET'))
        }
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "token_manager": manager_status,
            "environment_variables": env_check,
            "service": "fastmcp-lark-server",
            "version": "1.0.0"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": "Health check failed",
            "service": "fastmcp-lark-server"
        }

# MCP WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """MCP WebSocket endpoint"""
    await websocket.accept()
    try:
        # Handle MCP WebSocket connection
        await mcp.run_websocket(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close()

# MCP Tools
@mcp.tool()
async def send_message(
    receive_id: str,
    msg_type: str = "text",
    content: str = "",
    receive_id_type: str = "chat_id"
) -> Dict[str, Any]:
    """Send a message to a Lark chat or user"""
    try:
        token = await token_manager.get_tenant_access_token()
        url = f"{token_manager.base_url}/im/v1/messages"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": json.dumps({"text": content}) if msg_type == "text" else content
        }
        
        params = {"receive_id_type": receive_id_type}
        
        response = await http_client.post(url, headers=headers, json=payload, params=params)
        response.raise_for_status()
        data = response.json()
        
        if data.get('code') == 0:
            return {
                "success": True,
                "message_id": data['data']['message_id'],
                "data": data['data']
            }
        else:
            return {
                "success": False,
                "error": data.get('msg', 'Unknown error'),
                "code": data.get('code')
            }
            
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@mcp.tool()
async def get_chat_list(
    page_size: int = 20,
    page_token: str = ""
) -> Dict[str, Any]:
    """Get list of chats the bot has access to"""
    try:
        token = await token_manager.get_tenant_access_token()
        url = f"{token_manager.base_url}/im/v1/chats"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        params = {"page_size": page_size}
        if page_token:
            params["page_token"] = page_token
        
        response = await http_client.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        if data.get('code') == 0:
            return {
                "success": True,
                "chats": data['data']['items'],
                "page_token": data['data'].get('page_token'),
                "has_more": data['data'].get('has_more', False)
            }
        else:
            return {
                "success": False,
                "error": data.get('msg', 'Unknown error'),
                "code": data.get('code')
            }
            
    except Exception as e:
        logger.error(f"Error getting chat list: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@mcp.tool()
async def get_chat_members(
    chat_id: str,
    page_size: int = 20,
    page_token: str = ""
) -> Dict[str, Any]:
    """Get members of a specific chat"""
    try:
        token = await token_manager.get_tenant_access_token()
        url = f"{token_manager.base_url}/im/v1/chats/{chat_id}/members"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        params = {"page_size": page_size}
        if page_token:
            params["page_token"] = page_token
        
        response = await http_client.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        if data.get('code') == 0:
            return {
                "success": True,
                "members": data['data']['items'],
                "page_token": data['data'].get('page_token'),
                "has_more": data['data'].get('has_more', False)
            }
        else:
            return {
                "success": False,
                "error": data.get('msg', 'Unknown error'),
                "code": data.get('code')
            }
            
    except Exception as e:
        logger.error(f"Error getting chat members: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@mcp.tool()
async def create_calendar_event(
    summary: str,
    start_time: str,
    end_time: str,
    description: str = "",
    location: str = "",
    attendees: List[str] = []
) -> Dict[str, Any]:
    """Create a calendar event in Lark"""
    try:
        token = await token_manager.get_tenant_access_token()
        url = f"{token_manager.base_url}/calendar/v4/calendars/primary/events"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        event_data = {
            "summary": summary,
            "description": description,
            "start_time": {
                "timestamp": start_time
            },
            "end_time": {
                "timestamp": end_time
            }
        }
        
        if location:
            event_data["location"] = {"name": location}
        
        if attendees:
            event_data["attendees"] = [
                {"type": "user", "user_id": attendee} for attendee in attendees
            ]
        
        response = await http_client.post(url, headers=headers, json=event_data)
        response.raise_for_status()
        data = response.json()
        
        if data.get('code') == 0:
            return {
                "success": True,
                "event_id": data['data']['event']['event_id'],
                "event": data['data']['event']
            }
        else:
            return {
                "success": False,
                "error": data.get('msg', 'Unknown error'),
                "code": data.get('code')
            }
            
    except Exception as e:
        logger.error(f"Error creating calendar event: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@mcp.tool()
async def upload_file(
    file_path: str,
    file_type: str = "stream",
    parent_type: str = "im",
    parent_node: str = ""
) -> Dict[str, Any]:
    """Upload a file to Lark"""
    try:
        token = await token_manager.get_tenant_access_token()
        url = f"{token_manager.base_url}/im/v1/files"
        
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        # Read file content
        with open(file_path, 'rb') as f:
            files = {
                'file': (os.path.basename(file_path), f, 'application/octet-stream')
            }
            data = {
                'file_type': file_type,
                'parent_type': parent_type
            }
            if parent_node:
                data['parent_node'] = parent_node
            
            response = await http_client.post(url, headers=headers, files=files, data=data)
            response.raise_for_status()
            result = response.json()
        
        if result.get('code') == 0:
            return {
                "success": True,
                "file_key": result['data']['file_key'],
                "data": result['data']
            }
        else:
            return {
                "success": False,
                "error": result.get('msg', 'Unknown error'),
                "code": result.get('code')
            }
            
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@mcp.tool()
async def get_user_info(user_id: str) -> Dict[str, Any]:
    """Get information about a specific user"""
    try:
        token = await token_manager.get_tenant_access_token()
        url = f"{token_manager.base_url}/contact/v3/users/{user_id}"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = await http_client.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        if data.get('code') == 0:
            return {
                "success": True,
                "user": data['data']['user']
            }
        else:
            return {
                "success": False,
                "error": data.get('msg', 'Unknown error'),
                "code": data.get('code')
            }
            
    except Exception as e:
        logger.error(f"Error getting user info: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@mcp.tool()
async def create_doc(
    title: str,
    content: str = "",
    folder_token: str = ""
) -> Dict[str, Any]:
    """Create a new document in Lark Docs"""
    try:
        token = await token_manager.get_tenant_access_token()
        url = f"{token_manager.base_url}/docx/v1/documents"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        doc_data = {
            "title": title
        }
        
        if folder_token:
            doc_data["folder_token"] = folder_token
        
        response = await http_client.post(url, headers=headers, json=doc_data)
        response.raise_for_status()
        data = response.json()
        
        if data.get('code') == 0:
            document_id = data['data']['document']['document_id']
            
            # Add content if provided
            if content:
                await add_doc_content(document_id, content)
            
            return {
                "success": True,
                "document_id": document_id,
                "document": data['data']['document']
            }
        else:
            return {
                "success": False,
                "error": data.get('msg', 'Unknown error'),
                "code": data.get('code')
            }
            
    except Exception as e:
        logger.error(f"Error creating document: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def add_doc_content(document_id: str, content: str) -> bool:
    """Helper function to add content to a document"""
    try:
        token = await token_manager.get_tenant_access_token()
        url = f"{token_manager.base_url}/docx/v1/documents/{document_id}/blocks/batch_update"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "requests": [
                {
                    "insert_text": {
                        "location": {
                            "zone_id": "0"
                        },
                        "elements": [
                            {
                                "text_run": {
                                    "content": content
                                }
                            }
                        ]
                    }
                }
            ]
        }
        
        response = await http_client.patch(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        
        return data.get('code') == 0
        
    except Exception as e:
        logger.error(f"Error adding document content: {e}")
        return False

async def initialize_client():
    """Initialize the HTTP client and token manager"""
    global http_client, token_manager
    
    # Get environment variables
    app_id = os.getenv('LARK_APP_ID')
    app_secret = os.getenv('LARK_APP_SECRET')
    
    if not app_id or not app_secret:
        raise ValueError("LARK_APP_ID and LARK_APP_SECRET environment variables are required")
    
    # Initialize HTTP client
    http_client = httpx.AsyncClient(timeout=30.0)
    
    # Initialize token manager
    token_manager = LarkTokenManager(app_id, app_secret)
    
    logger.info("FastMCP Lark Server initialized successfully")

async def cleanup():
    """Cleanup resources"""
    global http_client
    if http_client:
        await http_client.aclose()

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    await initialize_client()

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await cleanup()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=True
    )
