import { Pool } from 'pg';

export type Plant = {
  id: string;
  name: string;
};

const pool = new Pool();

export async function fetchPlants(ownerId: string) {
  const query = `
    SELECT id, name
    FROM plants
    WHERE owner_id = $1
  `;

  return pool.query(query, [ownerId]);
}

export async function storeSnapshot(snapshot: string) {
  const sql = "INSERT INTO plant_snapshots (payload) VALUES ($1)";
  return pool.query(sql, [snapshot]);
}
