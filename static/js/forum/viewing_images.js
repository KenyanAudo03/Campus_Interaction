// Clicking Post edge to see Post details
document.addEventListener('DOMContentLoaded', () => {
    const posts = document.querySelectorAll('.post');

    posts.forEach(post => {
        const postLink = post.querySelector('.post-link');
        const postClickableArea = post.querySelector('.post-clickable-area');
        const likeButton = post.querySelector('.stat-item.likes');
        const interactiveElements = post.querySelectorAll(
            'button, .stat-item, .options-btn, .options-menu, ' +
            'a, input, textarea, .plyr, video, .media-container'
        );

        // Prevent clicks on interactive elements inside the post
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

        postClickableArea.addEventListener('click', (e) => {
            if (!e.target.closest('.post-content')) { // Don't navigate when clicking inside the content
                window.location.href = postLink.getAttribute('href');
            }
        });

        post.addEventListener('mouseenter', () => {
            post.classList.add('post-hover');
        });

        post.addEventListener('mouseleave', () => {
            post.classList.remove('post-hover');
        });
    });
});
