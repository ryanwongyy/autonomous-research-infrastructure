import { stopMockServer } from "./mock-server";

export default async function globalTeardown() {
  await stopMockServer();
  console.log("[global-teardown] Mock API server stopped");
}
