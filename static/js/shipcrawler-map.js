/* Shipcrawler Map — Leaflet.js vessel position */

const ShipcrawlerMap = (() => {
  let map = null;
  let marker = null;

  function render(lat, lon, vesselName) {
    const container = document.getElementById('map-container');
    if (!container) return;

    // Show the map card
    const mapCard = document.getElementById('map-card');
    if (mapCard) mapCard.style.display = 'block';

    if (!map) {
      map = L.map('map-container', {
        center: [lat, lon],
        zoom: 5,
        zoomControl: true,
        attributionControl: false,
        scrollWheelZoom: false,  // we handle this manually for cursor-based zoom
      });

      L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        maxZoom: 18,
      }).addTo(map);

      // Zoom toward mouse cursor instead of map center
      map.on('wheel', function(e) {
        e.originalEvent.preventDefault();
        const delta = e.originalEvent.deltaY;
        const zoomDelta = delta > 0 ? -1 : 1;
        const currentZoom = map.getZoom();
        const newZoom = Math.min(Math.max(currentZoom + zoomDelta, map.getMinZoom()), map.getMaxZoom());
        if (newZoom === currentZoom) return;
        const mouseLatLng = map.containerPointToLatLng(e.containerPoint);
        map.setView(mouseLatLng, newZoom, { animate: true });
      });

      marker = L.marker([lat, lon]).addTo(map);
      marker.bindPopup(`<b>${vesselName}</b><br>${lat}, ${lon}`);
    } else {
      map.setView([lat, lon], 5);
      if (marker) {
        marker.setLatLng([lat, lon]);
        marker.setPopupContent(`<b>${vesselName}</b><br>${lat}, ${lon}`);
      } else {
        marker = L.marker([lat, lon]).addTo(map);
        marker.bindPopup(`<b>${vesselName}</b><br>${lat}, ${lon}`);
      }
    }

    marker.openPopup();

    // Fix map rendering after becoming visible
    setTimeout(() => {
      map.invalidateSize();
    }, 300);
  }

  return { render };
})();
