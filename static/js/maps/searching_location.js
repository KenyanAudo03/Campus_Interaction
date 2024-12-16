// Searching

document.addEventListener("DOMContentLoaded", () => {
  const locations = document.querySelectorAll("#locationList li");
  const searchInput = document.getElementById("search");
  const searchButton = document.getElementById("searchButton");
  const recentSearchesList = document.getElementById("recentSearches");
  const mapFrame = document.getElementById("googleMap");
  const placesContainer = document.getElementById("places-container");
  const suggestionsContainer = document.getElementById("recent-suggestions");
  const closeSearchButton = document.getElementById("closeSearch");

  let recentSearches = [];
  let userLocation = null;
  const MAX_LOCATION_ATTEMPTS = 3;
  const API_KEY = ""; // Replace with your Google Maps API key

  const createStatusIndicator = () => {
    const statusDiv = document.createElement("div");
    statusDiv.id = "locationStatus";
    statusDiv.style.position = "fixed";
    statusDiv.style.bottom = "20px";
    statusDiv.style.left = "50%";
    statusDiv.style.transform = "translateX(-50%)";
    statusDiv.style.padding = "10px 20px";
    statusDiv.style.borderRadius = "5px";
    statusDiv.style.zIndex = "1000";
    statusDiv.style.backgroundColor = "rgba(0, 0, 0, 0.8)";
    statusDiv.style.color = "#fff";
    statusDiv.style.textAlign = "center";
    document.body.appendChild(statusDiv);
    return statusDiv;
  };

  const updateStatus = (message, isError = false) => {
    let statusDiv = document.getElementById("locationStatus");
    if (!statusDiv) {
      statusDiv = createStatusIndicator();
    }
    statusDiv.textContent = message;
    statusDiv.style.backgroundColor = isError ? "#ff5252" : "#4CAF50";
    statusDiv.style.color = "white";
    statusDiv.style.opacity = "1";
    if (!isError) {
      setTimeout(() => {
        statusDiv.style.opacity = "0";
        setTimeout(() => statusDiv.remove(), 500);
      }, 3000);
    }
  };

  const getLocationViaGeolocation = () => {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        reject(new Error("Geolocation is not supported by this browser."));
        return;
      }
      const options = {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 0,
      };
      navigator.geolocation.getCurrentPosition(
        (position) => {
          resolve({
            lat: position.coords.latitude,
            lng: position.coords.longitude,
            accuracy: position.coords.accuracy,
            source: "GPS",
          });
        },
        (error) => {
          reject(error);
        },
        options
      );
    });
  };

  const getLocationViaIP = async () => {
    try {
      const response = await fetch("https://ipapi.co/json/");
      const data = await response.json();
      if (data.latitude && data.longitude) {
        return {
          lat: data.latitude,
          lng: data.longitude,
          accuracy: 5000,
          source: "IP",
        };
      }
      throw new Error("Invalid IP geolocation response");
    } catch (error) {
      throw new Error("IP geolocation failed");
    }
  };

  const initializeMap = (location) => {
    sessionStorage.setItem("userLocation", JSON.stringify(location));
    mapFrame.src = `https://www.google.com/maps/embed/v1/view?key=${API_KEY}&center=${location.lat},${location.lng}&zoom=15`;
    const navigationLinks = document.querySelectorAll(".dropdown-content a");
    navigationLinks.forEach((link) => {
      const destination = link.textContent;
      link.href = `https://www.google.com/maps/dir/?api=1&origin=${
        location.lat
      },${location.lng}&destination=${encodeURIComponent(
        destination
      )}&travelmode=walking`;
    });
    updateStatus(`Location detected via ${location.source}!`);
  };

  const detectLocation = async () => {
    const storedLocation = sessionStorage.getItem("userLocation");
    if (storedLocation) {
      const location = JSON.parse(storedLocation);
      updateStatus("Using stored location");
      initializeMap(location);
      return;
    }
    updateStatus("Detecting your location...");
    try {
      const location = await getLocationViaGeolocation();
      initializeMap(location);
    } catch (error) {
      try {
        updateStatus("Trying IP-based location...", true);
        const location = await getLocationViaIP();
        initializeMap(location);
      } catch (ipError) {
        updateStatus("Using default location", true);
        initializeMap({
          lat: -1.2921,
          lng: 36.8219,
          accuracy: 10000,
          source: "Default",
        });
      }
    }
  };

  const performSearch = async (query) => {
    if (!query) return;
    const encodedQuery = encodeURIComponent(query);
    mapFrame.src = `https://www.google.com/maps/embed/v1/search?key=${API_KEY}&q=${encodedQuery}`;

    try {
      const response = await fetch("/maps/save-search/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCSRFToken(),
        },
        body: JSON.stringify({ query }),
      });
      const result = await response.json();
      if (result.success) {
        console.log(result.message);
      }
    } catch (error) {
      console.error("Error saving search:", error);
    }
    if (!recentSearches.includes(query)) {
      recentSearches.unshift(query);
      if (recentSearches.length > 5) {
        recentSearches.pop();
      }
      updateRecentSearches();
    }
    searchInput.value = "";
  };

  const getCSRFToken = () => {
    const cookies = document.cookie.split(";").reduce((acc, cookie) => {
      const [key, value] = cookie.trim().split("=");
      acc[key] = value;
      return acc;
    }, {});
    return cookies["csrftoken"];
  };

  const fetchRecentSearches = async () => {
    try {
      const response = await fetch("/maps/recent-searches/");
      if (!response.ok) {
        recentSearches = [];
        updateRecentSearches();
        return;
      }
      const searches = await response.json();
      recentSearches = searches.map((s) => s.query).slice(0, 5);
      updateRecentSearches();
    } catch (error) {
      console.error("Error fetching recent searches:", error);
      recentSearches = [];
      updateRecentSearches();
    }
  };

  const updateRecentSearches = () => {
    const header = `<div class="recent-suggestions-header">Recent Searches</div>`;
    
    if (recentSearches.length === 0) {
      suggestionsContainer.innerHTML = header + '<div class="no-recent-searches">No recent searches found.</div>';
    } else {
      const suggestions = recentSearches
        .map(
          (search) => `
            <div class="suggestion-item">${search}</div>`
        )
        .join("");
      
      suggestionsContainer.innerHTML = header + suggestions;
    }
  
    document.querySelectorAll(".suggestion-item").forEach((item) => {
      item.addEventListener("click", () => {
        performSearch(item.textContent);
        suggestionsContainer.style.display = "none";
      });
    });
  };
  
  

  searchButton.addEventListener("click", () => {
    const query = searchInput.value.trim();
    if (query) {
      performSearch(query);
    }
  });

  searchInput.addEventListener("keypress", (event) => {
    if (event.key === "Enter") {
      const query = searchInput.value.trim();
      if (query) {
        performSearch(query);
        suggestionsContainer.style.display = "none";
      }
    }
  });

  searchInput.addEventListener("focus", () => {
    if (recentSearches.length > 0) {
      suggestionsContainer.style.display = "block";
      updateRecentSearches();
    }
  });

  searchInput.addEventListener("input", () => {
    const query = searchInput.value.trim();
    if (query === "") {
      suggestionsContainer.style.display = "none";
    } else {
      suggestionsContainer.style.display = "block";
    }
  });

  closeSearchButton.addEventListener("click", () => {
    searchInput.value = "";
    suggestionsContainer.style.display = "none";
  });

  document.addEventListener("click", (event) => {
    if (
      !searchInput.contains(event.target) &&
      !suggestionsContainer.contains(event.target)
    ) {
      suggestionsContainer.style.display = "none";
    }
  });

  fetchRecentSearches();
  detectLocation();
});


// Show hide recent searches
document.addEventListener("DOMContentLoaded", () => {
  const searchInput = document.getElementById("search");
  const suggestionsContainer = document.getElementById("recent-suggestions");
  searchInput.addEventListener("input", () => {
      const query = searchInput.value.trim();
      
      if (query === "") {
          suggestionsContainer.classList.remove("show");
      } else {
          suggestionsContainer.classList.add("show");
      }
  });
  document.addEventListener("click", (event) => {
      const isClickOutside = 
          !searchInput.contains(event.target) && 
          !suggestionsContainer.contains(event.target);
      
      if (isClickOutside) {
          suggestionsContainer.classList.remove("show");
      }
  });
});

// Hide show search Input

document.addEventListener("DOMContentLoaded", () => {
  const searchContainer = document.getElementById("searchContainer");
  const closeSearch = document.getElementById("closeSearch");
  const openSearch = document.getElementById("openSearch");

  closeSearch.addEventListener("click", () => {
    searchContainer.style.display = "none";
    openSearch.classList.remove("hidden");
  });

  openSearch.addEventListener("click", () => {
    searchContainer.style.display = "flex";
    openSearch.classList.add("hidden");
  });
});