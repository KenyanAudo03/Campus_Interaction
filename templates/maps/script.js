document.addEventListener("DOMContentLoaded", () => {
  const mapFrame = document.getElementById("googleMap");
  const searchInput = document.getElementById("search");
  const searchButton = document.getElementById("searchButton");
  const dropdownLinks = document.querySelectorAll(".dropdown-content a");
  const recentSearchesContainer = document.getElementById("recentSearches");
  const universitySelector = document.getElementById("universitySelector");
  let userLocation = null;

  // Function to save recent searches in local storage
  const saveRecentSearch = (searchTerm) => {
    let recentSearches = JSON.parse(localStorage.getItem("recentSearches")) || [];
    if (!recentSearches.includes(searchTerm)) {
      recentSearches.push(searchTerm);
      localStorage.setItem("recentSearches", JSON.stringify(recentSearches));
      displayRecentSearches();
    }
  };

  // Function to display recent searches
  const displayRecentSearches = () => {
    let recentSearches = JSON.parse(localStorage.getItem("recentSearches")) || [];
    recentSearchesContainer.innerHTML = "";
    recentSearches.forEach((search) => {
      const searchItem = document.createElement("div");
      searchItem.classList.add("search-item");
      searchItem.innerHTML = `
        <span>${search}</span>
        <button class="delete-btn">&times;</button>
      `;
      searchItem.querySelector(".delete-btn").addEventListener("click", () => {
        removeRecentSearch(search);
      });
      searchItem.addEventListener("click", () => {
        searchLocation(search);
      });
      recentSearchesContainer.appendChild(searchItem);
    });
  };

  // Function to remove a recent search
  const removeRecentSearch = (searchTerm) => {
    let recentSearches = JSON.parse(localStorage.getItem("recentSearches")) || [];
    recentSearches = recentSearches.filter((search) => search !== searchTerm);
    localStorage.setItem("recentSearches", JSON.stringify(recentSearches));
    displayRecentSearches();
  };

  // Function to handle search
  const searchLocation = (location) => {
    mapFrame.src = `https://www.google.com/maps?q=${encodeURIComponent(location)}&output=embed`;
    saveRecentSearch(location);
  };

  // Event listener for search button
  searchButton.addEventListener("click", () => {
    const searchValue = searchInput.value.trim();
    if (searchValue) {
      searchLocation(searchValue);
      searchInput.value = "";
    } else {
      alert("Please enter a location to search.");
    }
  });

  // Get current location
  const getCurrentLocation = async () => {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        reject("Geolocation is not supported by your browser.");
      }
      navigator.geolocation.getCurrentPosition(
        (position) => resolve({ lat: position.coords.latitude, lng: position.coords.longitude }),
        (error) => reject(error)
      );
    });
  };

  // Initialize map with current location
  const initializeMap = async () => {
    try {
      userLocation = await getCurrentLocation();
      mapFrame.src = `https://www.google.com/maps?q=${userLocation.lat},${userLocation.lng}&output=embed`;
    } catch {
      userLocation = { lat: -1.2921, lng: 36.8219 }; // Default to Nairobi
      mapFrame.src = `https://www.google.com/maps?q=${userLocation.lat},${userLocation.lng}&output=embed`;
    }
  };

  // Handle dropdown link clicks for directions
  dropdownLinks.forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      const destination = link.textContent.trim();
      if (userLocation) {
        const directionsUrl = `https://www.google.com/maps/dir/?api=1&origin=${userLocation.lat},${userLocation.lng}&destination=${encodeURIComponent(destination)}&travelmode=walking`;
        window.open(directionsUrl, "_blank");
      } else {
        alert("Unable to detect your location. Please allow location access.");
      }
    });
  });

  // Handle university selector change
  universitySelector.addEventListener("change", (event) => {
    const [lat, lng] = event.target.value.split(",");
    mapFrame.src = `https://www.google.com/maps?q=${lat},${lng}&output=embed`;
  });

  // Load recent searches on page load
  displayRecentSearches();
  initializeMap();
});
