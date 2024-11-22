function toggleComments() {
    const commentsSection = document.getElementById('main-comments');
    const toggleButton = document.getElementById('toggleCommentsBtn');
    
    if (commentsSection.style.maxHeight) {
        // Collapse comments
        commentsSection.style.maxHeight = null; // Reset max-height
        toggleButton.innerHTML = '<i class="fas fa-comments"></i> Show Comments';
    } else {
        // Expand comments
        commentsSection.style.maxHeight = commentsSection.scrollHeight + "px";
        toggleButton.innerHTML = '<i class="fas fa-comments"></i> Hide Comments';
    }
}

// Ensure comments are collapsed by default on page load
document.addEventListener('DOMContentLoaded', () => {
    const commentsSection = document.getElementById('main-comments');
    commentsSection.style.maxHeight = null; // Start collapsed
});
