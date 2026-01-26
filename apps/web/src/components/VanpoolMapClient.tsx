'use client';

import { useMemo, useEffect } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, Tooltip, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import type { Employee } from '@prisma/client';

// Component to set the map view on mount
function SetViewOnMount({ center, zoom }: { center: [number, number]; zoom: number }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, zoom);
  }, [map, center, zoom]);
  return null;
}

export interface VanpoolMapClientProps {
  factoryCoords: { lat: number; lng: number };
  factoryName: string;
  employees: Employee[];
}

interface ZipCodeData {
  zipCode: string;
  count: number;
  lat: number;
  lng: number;
  city: string;
}

// Approximate zip code centroids for common areas
const ZIP_CODE_COORDS: Record<string, { lat: number; lng: number; city: string }> = {
  // Bay Area - Fremont area
  '94536': { lat: 37.5574, lng: -121.9827, city: 'Fremont' },
  '94538': { lat: 37.4949, lng: -121.9446, city: 'Fremont' },
  '94539': { lat: 37.5108, lng: -121.9298, city: 'Fremont' },
  '94560': { lat: 37.5175, lng: -122.0308, city: 'Newark' },
  '94587': { lat: 37.5934, lng: -122.0438, city: 'Union City' },
  '95035': { lat: 37.4323, lng: -121.8996, city: 'Milpitas' },
  '94541': { lat: 37.6547, lng: -122.0558, city: 'Hayward' },
  '94542': { lat: 37.6391, lng: -122.0178, city: 'Hayward' },
  '94544': { lat: 37.6280, lng: -122.0668, city: 'Hayward' },
  '94545': { lat: 37.6127, lng: -122.1028, city: 'Hayward' },
  '94546': { lat: 37.6941, lng: -122.0858, city: 'Castro Valley' },
  '94577': { lat: 37.7249, lng: -122.1561, city: 'San Leandro' },
  '94578': { lat: 37.7054, lng: -122.1238, city: 'San Leandro' },
  '94579': { lat: 37.6878, lng: -122.1508, city: 'San Leandro' },
  '95110': { lat: 37.3382, lng: -121.8863, city: 'San Jose' },
  '95112': { lat: 37.3541, lng: -121.8791, city: 'San Jose' },
  '95113': { lat: 37.3333, lng: -121.8907, city: 'San Jose' },
  '95050': { lat: 37.3541, lng: -121.9552, city: 'Santa Clara' },
  '95051': { lat: 37.3483, lng: -121.9844, city: 'Santa Clara' },
  '95054': { lat: 37.3925, lng: -121.9623, city: 'Santa Clara' },
  '94085': { lat: 37.3913, lng: -122.0183, city: 'Sunnyvale' },
  '94086': { lat: 37.3763, lng: -122.0238, city: 'Sunnyvale' },
  '94087': { lat: 37.3503, lng: -122.0358, city: 'Sunnyvale' },
  '94040': { lat: 37.3861, lng: -122.0839, city: 'Mountain View' },
  '94041': { lat: 37.3894, lng: -122.0819, city: 'Mountain View' },
  '94043': { lat: 37.4056, lng: -122.0775, city: 'Mountain View' },
  '94301': { lat: 37.4419, lng: -122.1430, city: 'Palo Alto' },
  '94306': { lat: 37.4153, lng: -122.1275, city: 'Palo Alto' },
  // Texas - Austin/Round Rock area
  '78664': { lat: 30.5083, lng: -97.6789, city: 'Round Rock' },
  '78665': { lat: 30.5652, lng: -97.6397, city: 'Round Rock' },
  '78681': { lat: 30.5217, lng: -97.7347, city: 'Round Rock' },
  '78660': { lat: 30.4421, lng: -97.5678, city: 'Pflugerville' },
  '78653': { lat: 30.4274, lng: -97.4858, city: 'Manor' },
  '78717': { lat: 30.4879, lng: -97.7558, city: 'Austin' },
  '78728': { lat: 30.4548, lng: -97.6858, city: 'Austin' },
  '78729': { lat: 30.4578, lng: -97.7558, city: 'Austin' },
  '78750': { lat: 30.4179, lng: -97.7958, city: 'Austin' },
  '78753': { lat: 30.3679, lng: -97.6858, city: 'Austin' },
  '78754': { lat: 30.3379, lng: -97.6558, city: 'Austin' },
  '78758': { lat: 30.3879, lng: -97.7158, city: 'Austin' },
  '78759': { lat: 30.3979, lng: -97.7558, city: 'Austin' },
  '76574': { lat: 30.5679, lng: -97.5558, city: 'Taylor' },
  '78626': { lat: 30.6279, lng: -97.6758, city: 'Georgetown' },
  '78628': { lat: 30.6679, lng: -97.7458, city: 'Georgetown' },
  '78634': { lat: 30.5679, lng: -97.4858, city: 'Hutto' },
  // Outlier cities
  '90026': { lat: 34.0775, lng: -118.2606, city: 'Los Angeles' },
  '92101': { lat: 32.7198, lng: -117.1628, city: 'San Diego' },
  '93721': { lat: 36.7378, lng: -119.7871, city: 'Fresno' },
  '95814': { lat: 38.5816, lng: -121.4944, city: 'Sacramento' },
};

export default function VanpoolMapClient({ factoryCoords, factoryName, employees }: VanpoolMapClientProps) {
  // Aggregate employees by zip code
  const zipCodeData = useMemo(() => {
    const counts = new Map<string, number>();
    employees.forEach((emp) => {
      const zip = emp.homeZip;
      counts.set(zip, (counts.get(zip) || 0) + 1);
    });

    const data: ZipCodeData[] = [];
    counts.forEach((count, zipCode) => {
      const coords = ZIP_CODE_COORDS[zipCode];
      if (coords) {
        data.push({
          zipCode,
          count,
          lat: coords.lat,
          lng: coords.lng,
          city: coords.city,
        });
      }
    });
    return data;
  }, [employees]);

  // Center on factory location by default
  const mapCenter: [number, number] = [factoryCoords.lat, factoryCoords.lng];

  const maxCount = useMemo(
    () => Math.max(...zipCodeData.map((z) => z.count), 1),
    [zipCodeData]
  );

  return (
    <div className="rounded-lg overflow-hidden border border-neutral-200">
      <style>{`
        .leaflet-container {
          height: 350px;
          width: 100%;
          background: #f5f5f5;
        }
      `}</style>

      <MapContainer
        key={`${factoryCoords.lat}-${factoryCoords.lng}`}
        center={mapCenter}
        zoom={11}
        scrollWheelZoom={true}
        style={{ height: '350px', width: '100%' }}
      >
        <SetViewOnMount center={mapCenter} zoom={11} />
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {/* Zip code circles */}
        {zipCodeData.map((zip) => {
          const radius = 8 + (zip.count / maxCount) * 12;
          const opacity = 0.5 + (zip.count / maxCount) * 0.3;
          
          return (
            <CircleMarker
              key={zip.zipCode}
              center={[zip.lat, zip.lng]}
              radius={radius}
              pathOptions={{
                fillColor: '#3b82f6',
                fillOpacity: opacity,
                color: '#1d4ed8',
                weight: 2,
              }}
            >
              <Tooltip direction="top" offset={[0, -5]}>
                <div className="text-sm">
                  <div className="font-semibold">{zip.zipCode}</div>
                  <div className="text-neutral-600">{zip.city}</div>
                  <div className="text-blue-600">
                    {zip.count} employee{zip.count !== 1 ? 's' : ''}
                  </div>
                </div>
              </Tooltip>
            </CircleMarker>
          );
        })}

        {/* Factory marker */}
        <CircleMarker
          center={[factoryCoords.lat, factoryCoords.lng]}
          radius={12}
          pathOptions={{
            fillColor: '#dc2626',
            fillOpacity: 1,
            color: '#ffffff',
            weight: 3,
          }}
        >
          <Popup>
            <div className="text-sm">
              <div className="font-semibold">{factoryName}</div>
              <div className="text-neutral-500">Work site</div>
            </div>
          </Popup>
          <Tooltip direction="top" offset={[0, -10]} permanent>
            <span className="font-medium">{factoryName}</span>
          </Tooltip>
        </CircleMarker>
      </MapContainer>

      {/* Legend */}
      <div className="px-4 py-3 bg-white border-t border-neutral-200 flex items-center justify-between text-xs text-neutral-600">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red-600 border-2 border-white shadow"></div>
            <span>Factory</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-full bg-blue-500 border border-blue-700"></div>
            <span>Employee zip codes (larger = more employees)</span>
          </div>
        </div>
        <div className="text-neutral-500">
          {zipCodeData.length} zip code{zipCodeData.length !== 1 ? 's' : ''} · {employees.length} employees
        </div>
      </div>
    </div>
  );
}
