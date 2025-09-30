import React, { useEffect, useState } from 'react';
import type { Plant } from '../utils/data';
import { fetchPlants } from '../utils/data';

export function Dashboard({ ownerId }: { ownerId: string }) {
  const [plants, setPlants] = useState<Plant[]>([]);

  useEffect(() => {
    fetchPlants(ownerId).then(setPlants);
  }, [ownerId]);

  return (
    <section>
      <h1>Plant Dashboard</h1>
      <ul>
        {plants.map((plant) => (
          <li key={plant.id}>{plant.name}</li>
        ))}
      </ul>
    </section>
  );
}

export const usePlantMetrics = () => {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setReady(true);
  }, []);

  return ready;
};
