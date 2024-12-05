document.addEventListener('DOMContentLoaded', () => {
    const posts = document.querySelectorAll('.post');

    posts.forEach(post => {
        const postLink = post.querySelector('.post-link');
        const likeButton = post.querySelector('.stat-item.likes');
        const interactiveElements = post.querySelectorAll(
            'button, .stat-item, .options-btn, .options-menu, ' +
            'a, input, textarea, .plyr, video, .media-container'
        );

        // Add click prevention to interactive elements
        interactiveElements.forEach(el => {
            el.addEventListener('click', (e) => {
                e.stopPropagation();
            });
        });

        // Prevent navigation when clicking the like button
        if (likeButton) {
            likeButton.addEventListener('click', (e) => {
                e.stopPropagation(); // Prevent parent post click
            });
        }

        // Navigate to post detail when clicking on post edges
        post.addEventListener('click', (e) => {
            if (postLink && !e.target.closest('.stat-item, .options-menu, button, a, .plyr, video')) {
                window.location.href = postLink.getAttribute('href');
            }
        });

        // Hover effect for post
        post.addEventListener('mouseenter', () => {
            post.classList.add('post-hover');
        });

        post.addEventListener('mouseleave', () => {
            post.classList.remove('post-hover');
        });
    });
});
