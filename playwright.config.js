module.exports = {
  testDir: "tests/e2e",
  // First run boots the webR runtime + downloads 3 packages over the network,
  // which is slow. Keep the per-test timeout generous.
  timeout: 240000,
  webServer: {
    command: "npm run serve",
    url: "http://localhost:8080",
    reuseExistingServer: true,
    timeout: 240000
  },
  use: { baseURL: "http://localhost:8080" }
};
