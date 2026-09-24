// ========== TRANSLATIONS ==========
const translations = {
    en: {
        connecting: 'Connecting...',
        connected: 'Connected',
        disconnected: 'Disconnected',
        select_station: 'Select station...',
        tab_current: 'Current',
        tab_charts: 'Charts',
        welcome_title: 'Select station on map',
        welcome_text: 'Click marker or select from list above',
        loading: 'Loading data...',
        temperature: 'Temperature',
        humidity: 'Humidity',
        pressure: 'Pressure',
        wind: 'Wind',
        lux: 'Light Intensity',
        ago: 'ago',
        system_info: 'System Information',
        lora_info: 'Additional LoRa Data',
        station: 'Station',
        battery: 'Battery',
        signal: 'Signal',
        wind_direction: 'Wind Direction',
        location: 'Location',
        select_station_btn: 'Select Station',
        type: 'Type',
        lora: 'LoRa',
        emulator: 'Emulator',
        official: 'Official'
    },
    pl: {
        connecting: 'Łączenie...',
        connected: 'Połączono',
        disconnected: 'Rozłączono',
        select_station: 'Wybierz stację...',
        tab_current: 'Aktualnie',
        tab_charts: 'Wykresy',
        welcome_title: 'Wybierz stację na mapie',
        welcome_text: 'Kliknij pinezkę lub wybierz z listy powyżej',
        loading: 'Ładowanie danych...',
        temperature: 'Temperatura',
        humidity: 'Wilgotność',
        pressure: 'Ciśnienie',
        wind: 'Wiatr',
        lux: 'Natężenie światła',
        ago: 'temu',
        system_info: 'Informacje systemowe',
        lora_info: 'Dodatkowe dane LoRa',
        station: 'Stacja',
        battery: 'Bateria',
        signal: 'Sygnał',
        wind_direction: 'Kierunek wiatru',
        location: 'Lokalizacja',
        select_station_btn: 'Wybierz stację',
        type: 'Typ',
        lora: 'LoRa',
        emulator: 'Emulator',
        official: 'Oficjalna'
    }
};

let currentLang = 'en';

function switchLanguage(lang) {
    currentLang = lang;

    document.querySelectorAll('.lang-btn').forEach(btn => {
        if (btn.dataset.lang === lang) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (translations[lang][key]) {
            el.textContent = translations[lang][key];
        }
    });

    if (currentStation && currentData[currentStation]) {
        updateCurrentView(currentData[currentStation]);
    }
}

function t(key) {
    return translations[currentLang][key] || key;
}

// ========== DYNAMICZNA KONFIGURACJA ==========
const isLocal = window.location.hostname.includes('10.58.40.97');
const isHTTPS = window.location.protocol === 'https:';

const INFLUX_CONFIG = isLocal ? {
    url: '/influx',
    token: 'my-super-secret-token',
    org: 'weather',
    bucket: 'weather_data'
} : {
    url: '/influxdb',
    token: 'my-super-secret-token',
    org: 'weather',
    bucket: 'weather_data'
};

const MQTT_URL = isLocal
    ? 'ws://10.58.40.97:9001/mqtt'
    : `${isHTTPS ? 'wss:' : 'ws:'}//${window.location.host}/mqtt`;

console.log('🌍 Mode:', isLocal ? 'LOCAL' : 'PUBLIC');
console.log('📡 MQTT:', MQTT_URL);
console.log('💾 InfluxDB:', INFLUX_CONFIG.url);



// ========== KONFIGURACJA STACJI ==========
let stations = [
    {
        id: "WEATHER_STATION_01",
        name: "Station 01 - Strzeszyn",
        lat: 52.443196,
        lng: 16.879174,
        location: "Strzeszyn, Poznań",
        type: "emulator"
    },
    {
        id: "WEATHER_STATION_02",
        name: "Station 02 - Winogrady",
        lat: 52.433196,
        lng: 16.889174,
        location: "Winogrady, Poznań",
        type: "emulator"
    },
    {
        id: "WEATHER_STATION_03",
        name: "Station 03 - Rataje",
        lat: 52.423196,
        lng: 16.949174,
        location: "Rataje, Poznań",
        type: "emulator"
    },
    {
        id: "station_ac1f09fffe1e035f",
        name: "Station LoRa - Gate N",
        lat: 52.430968906936855,
        lng: 16.8114048242569,
        location: "Gate_N - LoRa",
        type: "lora"
    },
    {
        id: "station_lawica",
        name: "EPPO - Lotnisko Ławica",
        lat: 52.421,
        lng: 16.826,
        location: "Poznań-Ławica Airport",
        type: "official",
        color: "#FF9800"
    }
];


let map = null;
let markers = {};
let currentStation = null;
let mqttClient = null;
let currentData = {};
let predictionData = {};
let charts = {
    temp: null,
    humidity: null,
    pressure: null,
    wind: null
};

document.addEventListener('DOMContentLoaded', () => {
    initMap();
    initMQTT();
    initTabs();
    initStationSelector();
    initDropdowns();
    loadAllStationsFromInfluxDB();
});

// ========== MAPA ==========
function initMap() {
    console.log('Initializing map...');

    map = L.map('map').setView([52.4064, 16.9252], 12);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 18
    }).addTo(map);

    markers = {};

    stations.forEach((station, index) => {
        console.log(`  ${index + 1}. ${station.id} → [${station.lat}, ${station.lng}]`);

        const color = station.type === 'lora' ? '#9C27B0' :
            station.type === 'official' ? '#FF9800' : '#4CAF50';

        const typeText = station.type === 'lora' ? 'LoRa' :
            station.type === 'official' ? 'Official' : 'Emulator';

        const marker = L.marker([station.lat, station.lng])
            .bindPopup(`
                <div style="min-width: 200px;">
                    <h3>${station.name}</h3>
                    <p><strong>ID:</strong> ${station.id}</p>
                    <p><strong>${t('location')}:</strong> ${station.location}</p>
                    <p><strong>${t('type')}:</strong> ${typeText}</p>
                    <button onclick="selectStation('${station.id}')" style="
                        padding: 8px 16px;
                        background: ${color};
                        color: white;
                        border: none;
                        border-radius: 4px;
                        cursor: pointer;
                        margin-top: 8px;
                    ">${t('select_station_btn')}</button>
                </div>
            `)
            .addTo(map);

        markers[station.id] = marker;
    });

    console.log(`Added ${Object.keys(markers).length} markers to map`);

    setTimeout(() => {
        const bounds = L.latLngBounds(
            stations.map(s => [s.lat, s.lng])
        );
        map.fitBounds(bounds, { padding: [50, 50] });
        console.log('Centered map on all stations');
    }, 500);
}

// ========== MQTT ==========
function initMQTT() {

    mqttClient = mqtt.connect(MQTT_URL);  // Używa dynamicznego URL z góry

    const statusDot = document.getElementById('mqtt-status');
    const statusText = document.getElementById('mqtt-status-text');

    mqttClient.on('connect', () => {
        console.log('Connected to MQTT');
        statusDot.classList.remove('disconnected');
        statusText.textContent = t('connected');

        mqttClient.subscribe('weather/station/data');
        mqttClient.subscribe('weather/predictions');
    });

    mqttClient.on('error', (error) => {
        console.error('MQTT error:', error);
        statusDot.classList.add('disconnected');
        statusText.textContent = t('disconnected');
    });

    mqttClient.on('message', (topic, message) => {
        try {
            const data = JSON.parse(message.toString());

            if (topic === 'weather/predictions') {
                handlePredictionUpdate(data);
            } else {
                handleDataUpdate(data);
            }
        } catch (e) {
            console.error('Parse error:', e);
        }
    });
}

// ========== PREDICTIONS ==========
function handlePredictionUpdate(data) {
    console.log('Received prediction:', data.station_id);
    predictionData[data.station_id] = data;

    if (currentStation === data.station_id) {
        updatePredictionsView(data);
    }
}

function updatePredictionsView(data) {
    document.getElementById('loading-predictions').style.display = 'none';
    const container = document.getElementById('predictions-data');
    container.style.display = 'block';

    const current = data.current;
    const predicted = data.predicted;

    const tempChange = predicted.temperature - current.temperature;
    const pressureChange = predicted.pressure - current.pressure;
    const humidityChange = predicted.humidity - current.humidity;

    container.innerHTML = `
        <h3 style="color: #667eea; margin-bottom: 10px;">ML Prediction (1 hour ahead)</h3>
        <p style="color: #718096; margin-bottom: 20px; font-size: 0.9em;">
            Current: ${new Date(data.current_time).toLocaleTimeString('pl-PL')} → 
            Prediction: ${new Date(data.prediction_time).toLocaleTimeString('pl-PL')}
        </p>
        
        <div class="parameter-card">
            <div class="parameter-header">
                <div class="parameter-label">
                    <span>Temperature</span>
                </div>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="width: 100%;">
                    <div style="font-size: 1.3em; color: #2d3748; margin-bottom: 8px;">
                        ${current.temperature.toFixed(1)}°C → <strong style="color: #667eea;">${predicted.temperature.toFixed(1)}°C</strong>
                    </div>
                    <div style="font-size: 0.9em; color: ${tempChange > 0 ? '#f56565' : '#48bb78'};">
                        ${tempChange > 0 ? '↑' : '↓'} ${Math.abs(tempChange).toFixed(2)}°C
                    </div>
                </div>
            </div>
        </div>
        
        <div class="parameter-card">
            <div class="parameter-header">
                <div class="parameter-label">
                    <span>Pressure</span>
                </div>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="width: 100%;">
                    <div style="font-size: 1.3em; color: #2d3748; margin-bottom: 8px;">
                        ${current.pressure.toFixed(1)} hPa → <strong style="color: #667eea;">${predicted.pressure.toFixed(1)} hPa</strong>
                    </div>
                    <div style="font-size: 0.9em; color: ${pressureChange > 0 ? '#48bb78' : '#f56565'};">
                        ${pressureChange > 0 ? '↑' : '↓'} ${Math.abs(pressureChange).toFixed(2)} hPa
                    </div>
                </div>
            </div>
        </div>
        
        <div class="parameter-card">
            <div class="parameter-header">
                <div class="parameter-label">
                    <span>Humidity</span>
                </div>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="width: 100%;">
                    <div style="font-size: 1.3em; color: #2d3748; margin-bottom: 8px;">
                        ${current.humidity.toFixed(1)}% → <strong style="color: #667eea;">${predicted.humidity.toFixed(1)}%</strong>
                    </div>
                    <div style="font-size: 0.9em; color: ${humidityChange > 0 ? '#48bb78' : '#f56565'};">
                        ${humidityChange > 0 ? '↑' : '↓'} ${Math.abs(humidityChange).toFixed(2)}%
                    </div>
                </div>
            </div>
        </div>
        
        <div class="system-info" style="margin-top: 20px;">
            <h3>ℹ️ Model Information</h3>
            <div class="info-row">
                <span class="info-label">Algorithm:</span>
                <span class="info-value">Gradient Boosting</span>
            </div>
            <div class="info-row">
                <span class="info-label">Features:</span>
                <span class="info-value">166 engineered</span>
            </div>
            <div class="info-row">
                <span class="info-label">Training data:</span>
                <span class="info-value">IMGW Poznań-Ławica 2025</span>
            </div>
            <div class="info-row">
                <span class="info-label">Evaluation:</span>
                <span class="info-value">being reworked (target leakage in feature set)</span>
            </div>
        </div>
    `;
}

// ========== OBSŁUGA DANYCH ==========
function handleDataUpdate(data) {
    updateStationLocation(data);

    if (!currentData[data.station_id]) {
        currentData[data.station_id] = {
            ...data,
            receivedAt: Date.now()
        };
    } else {
        const cached = currentData[data.station_id];

        currentData[data.station_id] = {
            ...cached,
            timestamp: data.timestamp,
            receivedAt: Date.now(),
            sensors: {
                temperature: data.sensors.temperature !== null && data.sensors.temperature !== undefined ? data.sensors.temperature : cached.sensors.temperature,
                humidity: data.sensors.humidity !== null && data.sensors.humidity !== undefined ? data.sensors.humidity : cached.sensors.humidity,
                pressure: data.sensors.pressure !== null && data.sensors.pressure !== undefined ? data.sensors.pressure : cached.sensors.pressure,
                wind_speed: data.sensors.wind_speed !== null && data.sensors.wind_speed !== undefined ? data.sensors.wind_speed : cached.sensors.wind_speed,
                wind_direction: data.sensors.wind_direction !== null && data.sensors.wind_direction !== undefined ? data.sensors.wind_direction : cached.sensors.wind_direction
            },
            battery_voltage: data.battery_voltage || cached.battery_voltage,
            signal_strength: data.signal_strength || cached.signal_strength,
            lat: data.lat || cached.lat,
            lng: data.lng || cached.lng,
            location: data.location || cached.location,
            is_lora: data.is_lora,
            lora_metadata: data.lora_metadata || cached.lora_metadata
        };
    }

    if (currentStation === data.station_id) {
        updateCurrentView(currentData[data.station_id]);
    }
}

function updateStationLocation(data) {
    if (!data.lat || !data.lng) return;

    const station = stations.find(s => s.id === data.station_id);
    if (!station) return;

    const latChanged = Math.abs(station.lat - data.lat) > 0.0001;
    const lngChanged = Math.abs(station.lng - data.lng) > 0.0001;

    if (latChanged || lngChanged) {
        console.log(`Location update ${data.station_id}: ${data.lat}, ${data.lng}`);

        station.lat = data.lat;
        station.lng = data.lng;
        station.location = data.location || station.location;

        if (markers[data.station_id]) {
            markers[data.station_id].setLatLng([data.lat, data.lng]);
        }
    }
}

async function loadAllStationsFromInfluxDB() {
    console.log('Loading last data from all stations...');

    for (const station of stations) {
        try {
            const lastData = await fetchLastReading(station.id);
            if (lastData) {
                currentData[station.id] = {
                    station_id: station.id,
                    timestamp: lastData.time,
                    sensors: {
                        temperature: lastData.temperature,
                        humidity: lastData.humidity,
                        pressure: lastData.pressure,
                        wind_speed: lastData.wind_speed,
                        wind_direction: lastData.wind_direction
                    },
                    battery_voltage: lastData.battery_voltage || 4.0,
                    signal_strength: lastData.signal_strength || -100,
                    lat: station.lat,
                    lng: station.lng,
                    location: station.location,
                    is_lora: station.type === 'lora',
                    receivedAt: Date.now()
                };
                console.log(`  ✓ ${station.id}: loaded`);
            }
        } catch (error) {
            console.error(`  ✗ ${station.id}: ${error.message}`);
        }
    }

    console.log('Loaded historical data');
}

async function fetchLastReading(stationId) {
    const query = `
        from(bucket: "${INFLUX_CONFIG.bucket}")
        |> range(start: -24h)
        |> filter(fn: (r) => r["_measurement"] == "weather_measurement")
        |> filter(fn: (r) => r["station_id"] == "${stationId}")
        |> last()
    `;

    try {
        const response = await fetch(`${INFLUX_CONFIG.url}/api/v2/query?org=${INFLUX_CONFIG.org}`, {
            method: 'POST',
            credentials: 'include', // <--- FIX: Dodano autoryzację sesji
            headers: {
                'Authorization': `Token ${INFLUX_CONFIG.token}`,
                'Content-Type': 'application/vnd.flux',
                'Accept': 'application/csv'
            },
            body: query
        });

        if (!response.ok) {
            throw new Error(`InfluxDB error: ${response.status}`);
        }

        const csv = await response.text();
        return parseLastReadingCSV(csv);
    } catch (error) {
        console.error(`Error fetching last reading for ${stationId}:`, error);
        return null;
    }
}

function parseLastReadingCSV(csv) {
    const lines = csv.trim().split('\n');
    const result = {
        time: null,
        temperature: null,
        humidity: null,
        pressure: null,
        wind_speed: null,
        wind_direction: null,
        battery_voltage: null,
        signal_strength: null
    };

    let headerLine = null;
    let timeIdx = -1;
    let fieldIdx = -1;
    let valueIdx = -1;

    for (let i = 0; i < lines.length; i++) {
        if (lines[i].includes('_time') && lines[i].includes('_field') && lines[i].includes('_value')) {
            headerLine = lines[i];
            const headers = headerLine.split(',');

            for (let j = 0; j < headers.length; j++) {
                if (headers[j] === '_time') timeIdx = j;
                if (headers[j] === '_field') fieldIdx = j;
                if (headers[j] === '_value') valueIdx = j;
            }
            break;
        }
    }

    if (timeIdx < 0 || fieldIdx < 0 || valueIdx < 0) {
        timeIdx = 5;
        fieldIdx = 7;
        valueIdx = 6;
    }

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];

        if (line.startsWith('#') || line.trim() === '' || line.includes('_measurement')) continue;

        const parts = line.split(',');

        if (parts.length <= Math.max(timeIdx, fieldIdx, valueIdx)) continue;

        const time = parts[timeIdx];
        const field = parts[fieldIdx];
        const valueStr = parts[valueIdx];
        const value = parseFloat(valueStr);

        if (!field || isNaN(value)) continue;

        if (!result.time && time) {
            result.time = time;
        }

        if (field === 'temperature') result.temperature = value;
        else if (field === 'humidity') result.humidity = value;
        else if (field === 'pressure') result.pressure = value;
        else if (field === 'wind_speed') result.wind_speed = value;
        else if (field === 'wind_direction') result.wind_direction = value;
        else if (field === 'battery_voltage') result.battery_voltage = value;
        else if (field === 'signal_strength') result.signal_strength = value;
    }

    if (!result.time && result.temperature === null && result.humidity === null) {
        return null;
    }

    return result;
}

// ========== TABS ==========
function initTabs() {
    const tabs = document.querySelectorAll('.tab');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const tabName = tab.dataset.tab;
            switchTab(tabName);
        });
    });
}

function switchTab(tabName) {
    document.querySelectorAll('.tab-pane').forEach(pane => {
        pane.classList.remove('active');
    });

    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
    });

    const targetPane = document.getElementById(`${tabName}-pane`);
    if (targetPane) {
        targetPane.classList.add('active');
    }

    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

    if (tabName === 'charts' && currentStation) {
        loadAllCharts();
    }

    if (tabName === 'predictions' && currentStation && predictionData[currentStation]) {
        updatePredictionsView(predictionData[currentStation]);
    }
}

function initDropdowns() {
    document.querySelectorAll('.time-range-button').forEach(button => {
        button.addEventListener('click', (e) => {
            e.stopPropagation();
            const chartType = button.dataset.chart;
            const menu = document.querySelector(`.time-range-menu[data-chart="${chartType}"]`);

            document.querySelectorAll('.time-range-menu').forEach(m => {
                if (m !== menu) m.classList.remove('active');
            });

            menu.classList.toggle('active');
        });
    });

    document.querySelectorAll('.time-range-option').forEach(option => {
        option.addEventListener('click', (e) => {
            const hours = parseInt(option.dataset.range);
            const menu = option.closest('.time-range-menu');
            const chartType = menu.dataset.chart;
            const button = document.querySelector(`.time-range-button[data-chart="${chartType}"]`);

            menu.querySelectorAll('.time-range-option').forEach(opt => {
                opt.classList.remove('selected');
            });
            option.classList.add('selected');

            button.textContent = option.textContent;

            menu.classList.remove('active');

            if (currentStation) {
                loadChart(chartType, hours);
            }
        });
    });

    document.addEventListener('click', () => {
        document.querySelectorAll('.time-range-menu').forEach(menu => {
            menu.classList.remove('active');
        });
    });
}

function initStationSelector() {
    const select = document.getElementById('station-select');

    select.addEventListener('change', (e) => {
        const stationId = e.target.value;
        if (stationId) {
            selectStation(stationId);
        }
    });
}

function selectStation(stationId) {
    currentStation = stationId;

    document.getElementById('station-select').value = stationId;
    document.getElementById('welcome-pane').style.display = 'none';

    switchTab('current');

    if (currentData[stationId]) {
        updateCurrentView(currentData[stationId]);
        document.getElementById('loading-current').style.display = 'none';
        document.getElementById('current-data').style.display = 'block';
    } else {
        document.getElementById('loading-current').style.display = 'block';
        document.getElementById('current-data').style.display = 'none';
    }

    const station = stations.find(s => s.id === stationId);
    if (station) {
        map.setView([station.lat, station.lng], 15);
        markers[stationId].openPopup();
    }
}

function updateCurrentView(data) {
    document.getElementById('loading-current').style.display = 'none';
    const container = document.getElementById('current-data');
    container.style.display = 'block';

    const receivedTime = data.receivedAt || Date.now();
    const age = Date.now() - receivedTime;
    const freshness = age < 30000 ? 'fresh' : (age < 300000 ? 'stale' : 'offline');
    const timeAgo = Math.floor(age / 1000);
    const timeText = timeAgo < 60 ? `${timeAgo}s ${t('ago')}` :
        timeAgo < 3600 ? `${Math.floor(timeAgo / 60)}min ${t('ago')}` :
            `${Math.floor(timeAgo / 3600)}h ${t('ago')}`;

    const displayValue = (value, unit = '') => {
        if (value === null || value === undefined) {
            return 'N/A';
        }
        return typeof value === 'number' ? value.toFixed(1) + unit : value + unit;
    };

    container.innerHTML = `
        <div class="parameter-card">
            <div class="parameter-header">
                <div class="parameter-label">
                    <span>${t('temperature')}</span>
                </div>
            </div>
            <div class="parameter-value">${displayValue(data.sensors.temperature, '°C')}</div>
            <div class="parameter-time">
                <div class="freshness-indicator ${freshness}"></div>
                ${timeText}
            </div>
        </div>
        
        <div class="parameter-card">
            <div class="parameter-header">
                <div class="parameter-label">
                    <span>${t('humidity')}</span>
                </div>
            </div>
            <div class="parameter-value">${displayValue(data.sensors.humidity, '%')}</div>
            <div class="parameter-time">
                <div class="freshness-indicator ${freshness}"></div>
                ${timeText}
            </div>
        </div>
        
        <div class="parameter-card">
            <div class="parameter-header">
                <div class="parameter-label">
                    <span>${t('pressure')}</span>
                </div>
            </div>
            <div class="parameter-value">${displayValue(data.sensors.pressure, ' hPa')}</div>
            <div class="parameter-time">
                <div class="freshness-indicator ${freshness}"></div>
                ${timeText}
            </div>
        </div>
        
        ${data.is_lora ? `
        <div class="parameter-card">
            <div class="parameter-header">
                <div class="parameter-label">
                    <span>${t('lux')}</span>
                </div>
            </div>
            <div class="parameter-value">${data.lora_metadata && data.lora_metadata.lux !== undefined ? data.lora_metadata.lux + ' lux' : 'N/A'}</div>
            <div class="parameter-time">
                <div class="freshness-indicator ${freshness}"></div>
                ${timeText}
            </div>
        </div>
        ` : `
        <div class="parameter-card">
            <div class="parameter-header">
                <div class="parameter-label">
                    <span>${t('wind')}</span>
                </div>
            </div>
            <div class="parameter-value">${displayValue(data.sensors.wind_speed, ' m/s')}</div>
            <div class="parameter-time">
                <div class="freshness-indicator ${freshness}"></div>
                ${timeText}
            </div>
        </div>
        `}
        
        <div class="system-info">
            <h3>${t('system_info')}</h3>
            <div class="info-row">
                <span class="info-label">${t('station')}:</span>
                <span class="info-value">${data.station_id}</span>
            </div>
            <div class="info-row">
                <span class="info-label">${t('battery')}:</span>
                <span class="info-value">${data.battery_voltage ? data.battery_voltage.toFixed(2) + 'V' : 'N/A'}</span>
            </div>
            <div class="info-row">
                <span class="info-label">${t('signal')}:</span>
                <span class="info-value">${data.signal_strength ? data.signal_strength + ' dBm' : 'N/A'}</span>
            </div>
            <div class="info-row">
                <span class="info-label">${t('wind_direction')}:</span>
                <span class="info-value">${displayValue(data.sensors.wind_direction, '°')}</span>
            </div>
        </div>
    `;

    if (data.is_lora && data.lora_metadata) {
        const meta = data.lora_metadata;
        let loraHtml = `
            <div class="system-info" style="margin-top: 20px;">
                <h3>${t('lora_info')}</h3>
        `;

        if (meta.cell1_voltage) {
            loraHtml += `
                <div class="info-row">
                    <span class="info-label">Cell 1:</span>
                    <span class="info-value">${meta.cell1_voltage.toFixed(3)}V</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Cell 2:</span>
                    <span class="info-value">${meta.cell2_voltage.toFixed(3)}V</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Cell 3:</span>
                    <span class="info-value">${meta.cell3_voltage.toFixed(3)}V</span>
                </div>
            `;
        }

        if (meta.temp_bms) {
            loraHtml += `
                <div class="info-row">
                    <span class="info-label">Temp BMS:</span>
                    <span class="info-value">${meta.temp_bms.toFixed(2)}°C</span>
                </div>
            `;
        }

        if (meta.temp_charger) {
            loraHtml += `
                <div class="info-row">
                    <span class="info-label">Temp Charger:</span>
                    <span class="info-value">${meta.temp_charger.toFixed(2)}°C</span>
                </div>
            `;
        }

        if (meta.temp_bmp390) {
            loraHtml += `
                <div class="info-row">
                    <span class="info-label">Temp BMP390:</span>
                    <span class="info-value">${meta.temp_bmp390.toFixed(2)}°C</span>
                </div>
            `;
        }

        // Wind speed (moved from main panel for LoRa stations)
        loraHtml += `
            <div class="info-row">
                <span class="info-label">${t('wind')}:</span>
                <span class="info-value">${data.sensors.wind_speed !== null && data.sensors.wind_speed !== undefined ? data.sensors.wind_speed.toFixed(1) + ' m/s' : 'N/A'}</span>
            </div>
        `;

        if (meta.white_ratio) {
            loraHtml += `
                <div class="info-row">
                    <span class="info-label">White Ratio:</span>
                    <span class="info-value">${meta.white_ratio.toFixed(2)}</span>
                </div>
            `;
        }

        if (meta.snr !== undefined) {
            loraHtml += `
                <div class="info-row">
                    <span class="info-label">SNR:</span>
                    <span class="info-value">${meta.snr.toFixed(1)} dB</span>
                </div>
            `;
        }

        loraHtml += `</div>`;
        container.innerHTML += loraHtml;
    }
}

// ========== CHARTS (bez zmian) ==========
function loadAllCharts() {
    loadChart('temp', getSelectedRange('temp'));
    loadChart('humidity', getSelectedRange('humidity'));
    loadChart('pressure', getSelectedRange('pressure'));
    loadChart('wind', getSelectedRange('wind'));
}

function getSelectedRange(chartType) {
    const menu = document.querySelector(`.time-range-menu[data-chart="${chartType}"]`);
    const selected = menu.querySelector('.time-range-option.selected');
    return parseInt(selected.dataset.range);
}

async function loadChart(chartType, hours) {
    if (!currentStation) return;

    const fieldMap = {
        temp: 'temperature',
        humidity: 'humidity',
        pressure: 'pressure',
        wind: 'wind_speed'
    };

    const labelMap = {
        temp: `${t('temperature')} (°C)`,
        humidity: `${t('humidity')} (%)`,
        pressure: `${t('pressure')} (hPa)`,
        wind: `${t('wind')} (m/s)`
    };

    const unitMap = {
        temp: '°C',
        humidity: '%',
        pressure: ' hPa',
        wind: ' m/s'
    };

    const colorMap = {
        temp: { border: '#667eea', bg: 'rgba(102, 126, 234, 0.1)' },
        humidity: { border: '#48bb78', bg: 'rgba(72, 187, 120, 0.1)' },
        pressure: { border: '#f6ad55', bg: 'rgba(246, 173, 85, 0.1)' },
        wind: { border: '#a0aec0', bg: 'rgba(160, 174, 192, 0.1)' }
    };

    const field = fieldMap[chartType];
    const label = labelMap[chartType];
    const unit = unitMap[chartType];
    const colors = colorMap[chartType];

    try {
        const data = await fetchInfluxData(currentStation, field, hours);

        if (data && data.length > 0) {
            const labels = data.map(point => {
                const date = new Date(point.time);
                if (hours <= 3) {
                    return date.getHours().toString().padStart(2, '0') + ':' +
                        date.getMinutes().toString().padStart(2, '0');
                } else if (hours <= 24) {
                    return date.getHours().toString().padStart(2, '0') + ':' +
                        date.getMinutes().toString().padStart(2, '0');
                } else {
                    return date.getDate() + '/' + (date.getMonth() + 1) + ' ' +
                        date.getHours().toString().padStart(2, '0') + ':00';
                }
            });
            const values = data.map(point => point.value);

            renderChart(chartType, labels, values, label, unit, colors);
        }
    } catch (error) {
        console.error(`Error loading ${chartType}:`, error);
    }
}

async function fetchInfluxData(stationId, field, hours) {
    const query = `
        from(bucket: "${INFLUX_CONFIG.bucket}")
        |> range(start: -${hours}h)
        |> filter(fn: (r) => r["_measurement"] == "weather_measurement")
        |> filter(fn: (r) => r["_field"] == "${field}")
        |> filter(fn: (r) => r["station_id"] == "${stationId}")
        |> aggregateWindow(every: ${hours >= 168 ? '2h' : hours >= 48 ? '1h' : hours >= 24 ? '30m' : hours >= 6 ? '10m' : '5m'}, fn: mean, createEmpty: false)
        |> yield(name: "mean")
    `;

    try {
        const response = await fetch(`${INFLUX_CONFIG.url}/api/v2/query?org=${INFLUX_CONFIG.org}`, {
            method: 'POST',
            credentials: 'include', // <--- FIX: Dodano autoryzację sesji
            headers: {
                'Authorization': `Token ${INFLUX_CONFIG.token}`,
                'Content-Type': 'application/vnd.flux',
                'Accept': 'application/csv'
            },
            body: query
        });

        if (!response.ok) {
            throw new Error(`InfluxDB error: ${response.status}`);
        }

        const csv = await response.text();
        return parseInfluxCSV(csv);
    } catch (error) {
        console.error('InfluxDB query error:', error);
        return null;
    }
}

function parseInfluxCSV(csv) {
    const lines = csv.trim().split('\n');
    const data = [];
    let headerFound = false;

    for (let line of lines) {
        if (line.startsWith('#')) continue;
        if (line.includes('_time') && line.includes('_value')) {
            headerFound = true;
            continue;
        }
        if (!headerFound && line.includes(',result,')) {
            headerFound = true;
            continue;
        }
        if (!line.trim()) continue;

        const parts = line.split(',');
        if (parts.length < 7) continue;

        try {
            const time = parts[5];
            const value = parseFloat(parts[6]);

            if (time && !isNaN(value)) {
                data.push({ time: time, value: value });
            }
        } catch (e) {
            continue;
        }
    }

    return data;
}

function renderChart(chartType, labels, data, label, unit, colors) {
    const canvasId = chartType === 'temp' ? 'tempChart' :
        chartType === 'humidity' ? 'humidityChart' :
            chartType === 'pressure' ? 'pressureChart' : 'windChart';

    const ctx = document.getElementById(canvasId).getContext('2d');

    if (charts[chartType]) {
        charts[chartType].destroy();
    }

    charts[chartType] = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: label,
                data: data,
                borderColor: colors.border,
                backgroundColor: colors.bg,
                tension: 0.4,
                fill: true,
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            return context.parsed.y.toFixed(1) + unit;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: false,
                    ticks: {
                        callback: function (value) {
                            return value.toFixed(1) + unit;
                        }
                    }
                },
                x: {
                    ticks: {
                        maxTicksLimit: 10
                    }
                }
            }
        }
    });
}

