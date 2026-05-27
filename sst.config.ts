/// <reference path="./.sst/platform/config.d.ts" />

export default $config({
  app(input) {
    const awsRegion = process.env.AWS_REGION ?? "us-east-2";
    const awsProfile = process.env.AWS_PROFILE;

    return {
      name: "palace-toolkit-docs",
      removal: input?.stage === "production" ? "retain" : "remove",
      home: "aws",
      providers: {
        aws: awsProfile
          ? {
              region: awsRegion,
              profile: awsProfile,
            }
          : {
              region: awsRegion,
            },
      },
    };
  },
  async run() {
    const routerDistributionId = process.env.EPSILON_FORGE_ROUTER_DISTRIBUTION_ID;

    if (!routerDistributionId) {
      throw new Error(
        "Missing EPSILON_FORGE_ROUTER_DISTRIBUTION_ID. Set it to the Router distribution ID output by epsilon-forge-website.",
      );
    }

    const router = sst.aws.Router.get("EpsilonForgeRouter", routerDistributionId);

    const docs = new sst.aws.StaticSite("PalaceToolkitDocs", {
      path: ".",
      build: {
        command: "mkdocs build",
        output: "site",
      },
      router: {
        instance: router,
        path: "/palace-toolkit",
      },
    });

    return {
      docs: docs.url,
      routerDistributionId,
    };
  },
});
