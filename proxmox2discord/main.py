from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from .endpoints import router
from . import discord
from .log_cleanup import periodic_cleanup_task, cleanup_old_logs

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup: run initial cleanup and start periodic task
    cleanup_task = None
    try:
        # Run initial cleanup in background to avoid blocking startup
        asyncio.create_task(cleanup_old_logs())
        logger.info("Scheduled initial log cleanup")
        
        # Start periodic cleanup task
        cleanup_task = asyncio.create_task(periodic_cleanup_task())
        logger.info("Started periodic log cleanup task")
        
        yield
    finally:
        # Shutdown: close HTTP client if it was created
        if cleanup_task:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass
        
        if discord._http_client is not None:
            await discord._http_client.aclose()


def create_app() -> FastAPI:
    app = FastAPI(
        title='Proxmox2Discord',
        description='Proxmox Discord notifier service',
        lifespan=lifespan,
        docs_url=None,  # Disable default docs to use custom one
        redoc_url="/redoc",
        swagger_ui_parameters={
            "syntaxHighlight.theme": "monokai",
        },
    )
    
    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        return HTMLResponse(content=f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{app.title} - Swagger UI</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
    <style>
        body {{
            margin: 0;
            background: #1a1a1a;
        }}
        
        /* Comprehensive dark mode for Swagger UI */
        .swagger-ui {{
            background: #1a1a1a;
            color: #e8e8e8;
        }}
        
        .swagger-ui .info .title {{
            color: #e8e8e8;
        }}
        
        .swagger-ui .info .title small {{
            background: #333;
            color: #e8e8e8;
        }}
        
        .swagger-ui .opblock-tag {{
            color: #e8e8e8;
            border-bottom: 1px solid #3a3a3a;
        }}
        
        .swagger-ui .opblock {{
            background: #252525;
            border: 1px solid #3a3a3a;
        }}
        
        .swagger-ui .opblock .opblock-summary {{
            background: #2d2d2d;
            border-color: #3a3a3a;
        }}
        
        .swagger-ui .opblock .opblock-summary:hover {{
            background: #353535;
        }}
        
        .swagger-ui .opblock-description-wrapper p,
        .swagger-ui .opblock-external-docs-wrapper p,
        .swagger-ui .opblock-title_normal p {{
            color: #e8e8e8;
        }}
        
        .swagger-ui .opblock .opblock-section-header {{
            background: #2d2d2d;
            border-color: #3a3a3a;
        }}
        
        .swagger-ui .opblock .opblock-section-header h4 {{
            color: #e8e8e8;
        }}
        
        .swagger-ui table thead tr th,
        .swagger-ui table thead tr td {{
            color: #e8e8e8;
            border-color: #3a3a3a;
        }}
        
        .swagger-ui .parameter__name,
        .swagger-ui .parameter__type {{
            color: #e8e8e8;
        }}
        
        .swagger-ui .response-col_status {{
            color: #e8e8e8;
        }}
        
        .swagger-ui .response-col_description__inner span {{
            color: #e8e8e8;
        }}
        
        .swagger-ui .responses-inner h4,
        .swagger-ui .responses-inner h5 {{
            color: #e8e8e8;
        }}
        
        .swagger-ui .scheme-container {{
            background: #252525;
            border: 1px solid #3a3a3a;
        }}
        
        .swagger-ui .loading-container .loading:after {{
            color: #e8e8e8;
        }}
        
        .swagger-ui .model-box {{
            background: #252525;
            border: 1px solid #3a3a3a;
        }}
        
        .swagger-ui .model {{
            color: #e8e8e8;
        }}
        
        .swagger-ui .prop-type {{
            color: #8bc34a;
        }}
        
        .swagger-ui table tbody tr td {{
            color: #e8e8e8;
            border-color: #3a3a3a;
        }}
        
        .swagger-ui .topbar {{
            background-color: #2d2d2d;
            border-bottom: 1px solid #3a3a3a;
        }}
        
        .swagger-ui .info a {{
            color: #8ab4f8;
        }}
        
        .swagger-ui .info a:hover {{
            color: #adc6ff;
        }}
        
        .swagger-ui .btn {{
            background: #3a3a3a;
            color: #e8e8e8;
            border-color: #5a5a5a;
        }}
        
        .swagger-ui .btn:hover {{
            background: #4a4a4a;
        }}
        
        .swagger-ui input[type=text],
        .swagger-ui textarea {{
            background: #2d2d2d;
            color: #e8e8e8;
            border: 1px solid #3a3a3a;
        }}
        
        .swagger-ui select {{
            background: #2d2d2d;
            color: #e8e8e8;
            border: 1px solid #3a3a3a;
        }}
        
        .swagger-ui .dialog-ux .modal-ux-content {{
            background: #252525;
            border: 2px solid #3a3a3a;
        }}
        
        .swagger-ui .model-title {{
            color: #e8e8e8;
        }}
        
        .swagger-ui .markdown code {{
            background: #2d2d2d;
            color: #f8f8f2;
        }}
        
        .swagger-ui .renderedMarkdown p,
        .swagger-ui .renderedMarkdown li {{
            color: #e8e8e8;
        }}
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
        window.onload = function() {{
            window.ui = SwaggerUIBundle({{
                url: "{app.openapi_url}",
                dom_id: '#swagger-ui',
                deepLinking: true,
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIBundle.SwaggerUIStandalonePreset
                ],
                layout: "BaseLayout",
                syntaxHighlight: {{
                    theme: "monokai"
                }},
                persistAuthorization: true,
                filter: true
            }});
        }};
    </script>
</body>
</html>
        """, media_type="text/html")

    app.include_router(router)

    return app


app = create_app()

