document.addEventListener('DOMContentLoaded', () => {
    const timestampEl = document.getElementById('timestamp');
    const devicesContainer = document.getElementById('devices-container');
    let autoRefresh = true;

    async function updateData() {
        try {
            const response = await fetch('/api/data');
            const data = await response.json();
            
            timestampEl.textContent = new Date(data.timestamp).toLocaleTimeString();
            
            devicesContainer.innerHTML = '';
            
            for (const [name, device] of Object.entries(data.devices)) {
                const card = document.createElement('div');
                card.className = 'device-card';
                card.innerHTML = `
                    <h3>${name}</h3>
                    <p>IP: ${device.ip}</p>
                    <p class="${device.reachable ? 'online' : 'offline'}">
                        <span class="status-badge"></span>
                        ${device.reachable ? `Online (${device.latency} ms)` : 'Offline'}
                    </p>
                `;
                devicesContainer.appendChild(card);
            }
        } catch (error) {
            console.error('Failed to fetch data:', error);
        }
    }

    document.getElementById('device-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        
        try {
            const response = await fetch('/api/devices', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    name: formData.get('name'),
                    ip: formData.get('ip')
                })
            });

            if (response.ok) {
                alert('Device added successfully!');
                e.target.reset();
                updateData();
            } else {
                alert('Failed to add device');
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Network error - check console');
        }
    });

    // Auto-refresh every 2 seconds
    setInterval(() => {
        if (autoRefresh) updateData();
    }, 2000);

    // Initial load
    updateData();
});
