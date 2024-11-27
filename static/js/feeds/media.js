const videoObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        const video = entry.target;
        if (!entry.isIntersecting && !video.paused) {
            video.pause();
        }
    });
}, {
    threshold: 0.2 
});

function observeVideos() {
    const videos = document.querySelectorAll('.post-media[controls]');
    videos.forEach(video => videoObserver.observe(video));
}

function previewMedia(input, type) {
    const previewContainer = document.getElementById(`${type}-preview`);
    previewContainer.innerHTML = ''; 
    
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        
        reader.onload = function(e) {
            const preview = document.createElement('div');
            preview.className = 'position-relative mt-2';
            
            const removeBtn = document.createElement('button');
            removeBtn.className = 'btn btn-danger btn-floating btn-sm position-absolute top-0 end-0 m-1';
            removeBtn.innerHTML = '<i class="fas fa-times"></i>';
            removeBtn.onclick = function() {
                input.value = '';
                previewContainer.innerHTML = '';
            };
            
            if (type === 'image') {
                preview.innerHTML = `
                    <img src="${e.target.result}" class="img-fluid rounded" alt="Preview">
                `;
            } else {
                preview.innerHTML = `
                    <video class="w-100 rounded" controls>
                        <source src="${e.target.result}" type="${input.files[0].type}">
                        Your browser does not support the video tag.
                    </video>
                `;
            }
            
            preview.appendChild(removeBtn);
            previewContainer.appendChild(preview);
        };
        
        reader.readAsDataURL(input.files[0]);
    }
} 