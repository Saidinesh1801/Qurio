import time
import hashlib
from django.http import JsonResponse


class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.requests = {}
        self.max_requests = 60
        self.window_seconds = 60

    def __call__(self, request):
        client_ip = self.get_client_ip(request)
        identifier = f"{client_ip}:{request.path}"
        
        current_time = time.time()
        
        if identifier not in self.requests:
            self.requests[identifier] = []
        
        self.requests[identifier] = [
            t for t in self.requests[identifier]
            if current_time - t < self.window_seconds
        ]
        
        if len(self.requests[identifier]) >= self.max_requests:
            return JsonResponse({
                'error': 'Rate limit exceeded',
                'retry_after': int(self.requests[identifier][0] + self.window_seconds - current_time)
            }, status=429)
        
        self.requests[identifier].append(current_time)
        
        response = self.get_response(request)
        
        response['X-RateLimit-Limit'] = str(self.max_requests)
        response['X-RateLimit-Remaining'] = str(self.max_requests - len(self.requests[identifier]))
        
        return response

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '127.0.0.1')
