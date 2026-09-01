import type { OpenNextConfig } from "@opennextjs/cloudflare";

const config: OpenNextConfig = {
  default: {
    override: {
      wrapper: "cloudflare-node",
      converter: "edge",
      // Remove the worker self reference binding
      incrementalCache: "dummy",
      tagCache: "dummy",
    },
  },
};

export default config;
