let currentPage = 1;
let loading = false;
let hasMore = false; // This will be set from the template

function handleScroll() {
    if (loading || !hasMore) return;

    const lastPost = document.querySelector('#posts-container .card:last-child');
    if (!lastPost) return;

    const lastPostOffset = lastPost.offsetTop + lastPost.clientHeight;
    const pageOffset = window.pageYOffset + window.innerHeight;

    if (pageOffset > lastPostOffset - 20) {
        loadMorePosts();
    }
}

function loadMorePosts() {
    if (loading || !hasMore) return;
    loading = true;

    const nextPage = currentPage + 1;
    const loadingIndicator = document.getElementById('loading-indicator');
    loadingIndicator.classList.remove('d-none');

    fetch(`/feeds/load-more-posts/?page=${nextPage}&trending=${isTrending}`)
        .then(response => response.json())
        .then(data => {
            const postsContainer = document.getElementById('posts-container');
            data.posts.forEach(post => {
                const postElement = createPostElement(post);
                postsContainer.appendChild(postElement);
            });
            
            // Observe any new videos
            observeVideos();
            
            currentPage = data.current_page;
            hasMore = data.has_next;
            loading = false;
            loadingIndicator.classList.add('d-none');
        })
        .catch(error => {
            console.error('Error loading more posts:', error);
            loading = false;
            loadingIndicator.classList.add('d-none');
        });
}

window.addEventListener('scroll', handleScroll); 