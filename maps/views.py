from django.shortcuts import render
from django.views import View
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import RecentSearch
import json

def maps(request):
    if request.user.is_authenticated:
        searches = RecentSearch.objects.filter(user=request.user).order_by('-timestamp')[:5]
        recent_searches = [search.query for search in searches]
    else:
        recent_searches = []
    return render(request, "maps/maps.html", {"recent_searches": recent_searches})


def recent_searches(request):
    if request.user.is_authenticated:
        searches = RecentSearch.objects.filter(user=request.user).order_by('-timestamp')[:5]
        recent_searches = [{"query": search.query} for search in searches]
    else:
        recent_searches = []
    print(recent_searches)

    return JsonResponse(recent_searches, safe=False)


@csrf_exempt
def save_search(request):
    if request.method == "POST" and request.user.is_authenticated:
        data = json.loads(request.body)
        query = data.get("query")
        if query:
            RecentSearch.objects.update_or_create(user=request.user, query=query)
            return JsonResponse({"success": True, "message": "Search saved successfully!"})
    return JsonResponse({"success": False, "message": "Failed to save search!"})