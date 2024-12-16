from django.shortcuts import render, redirect
from .models import Resource
from .forms import ResourceForm

# View to list all resources
def resource_list(request):
    resources = Resource.objects.all()
    
    # Process resources to add file type attributes for easier checking in the template
    for resource in resources:
        # Get file extension
        file_extension = resource.file.name.split('.')[-1].lower()
        resource.file_extension = file_extension
        
        # Add a boolean flag to check if the resource is an image
        resource.is_image = file_extension in ['jpg', 'jpeg', 'png']
        resource.is_pdf = file_extension == 'pdf'
    
    return render(request, 'resources/resource_list.html', {'resources': resources})

# View to upload a resource
def upload_resource(request):
    if request.method == 'POST':
        form = ResourceForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('resources')  # Redirect to the resources list after successful upload
    else:
        form = ResourceForm()
    return render(request, 'resources/upload_resource.html', {'form': form})

# View to filter resources by category
def resources_by_category(request, category):
    resources = Resource.objects.filter(category=category)
    
    # Process resources to add file type attributes for easier checking in the template
    for resource in resources:
        file_extension = resource.file.name.split('.')[-1].lower()
        resource.file_extension = file_extension
        resource.is_image = file_extension in ['jpg', 'jpeg', 'png']
        resource.is_pdf = file_extension == 'pdf'
    
    return render(request, 'resources/resource_list.html', {'resources': resources})
