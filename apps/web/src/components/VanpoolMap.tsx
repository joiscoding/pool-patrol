'use client';

import dynamic from 'next/dynamic';
import type { Employee } from '@prisma/client';

export interface VanpoolMapProps {
  factoryCoords: { lat: number; lng: number };
  factoryName: string;
  employees: Employee[];
}

// Dynamically import the map implementation to avoid SSR issues with Leaflet
const VanpoolMapClient = dynamic<VanpoolMapProps>(
  () => import('./VanpoolMapClient').then((mod) => mod.default),
  { 
    ssr: false,
    loading: () => (
      <div className="bg-neutral-100 rounded-lg h-[350px] flex items-center justify-center">
        <div className="text-neutral-500 text-sm">Loading map...</div>
      </div>
    ),
  }
);

export function VanpoolMap({ factoryCoords, factoryName, employees }: VanpoolMapProps) {
  return (
    <VanpoolMapClient
      factoryCoords={factoryCoords}
      factoryName={factoryName}
      employees={employees}
    />
  );
}
