import { startMockServer } from "./mock-server";

export default async function globalSetup() {
  const port = await startMockServer();
  console.log(`[global-setup] Mock API server started on port ${port}`);
}
