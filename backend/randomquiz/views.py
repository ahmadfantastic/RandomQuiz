from django.http import HttpResponse
from pathlib import Path
import os

def serve_react_app(request):
    """Serve the React app's index.html for all non-API routes."""
    index_path = Path(__file__).resolve().parent.parent.parent / 'frontend' / 'dist' / 'index.html'
    
    if index_path.exists():
        with open(index_path, 'r') as f:
            return HttpResponse(f.read(), content_type='text/html')
    else:
        return HttpResponse(
            '<h1>Frontend not built</h1><p>Run: cd frontend && npm run build</p>',
            content_type='text/html',
            status=404
        )
