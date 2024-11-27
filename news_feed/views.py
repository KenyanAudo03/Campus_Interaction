from django.shortcuts import render, redirect
from .forms import NewsForm
from .models import News

# Form for adding news articles
def add_news(request):
    if request.method == 'POST':
        form = NewsForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('news_list') 
    else:
        form = NewsForm()
    return render(request, 'news_feed/add_news.html', {'form': form})

def news_list(request):
    news = News.objects.all()
    return render(request, 'news_feed/news_list.html', {'news': news})
