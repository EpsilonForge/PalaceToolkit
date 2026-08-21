# Deploying Docs

This document records two ways to publish the built documentation site:

1. **EpsilonForge.com (SST + AWS CloudFront Router)** — the original setup,
   removed from this repo but kept here so it can be reproduced in another
   package.
2. **GitHub Pages** — the current deployment used by this repo.

## 1. EpsilonForge.com / PalaceToolkit (removed from this repo)

> Note: This section is a historical record. The files described below have
> been deleted from this repository and the docs are now deployed to GitHub
> Pages instead. The steps are documented here so they can be reproduced in a
> different package that still targets the shared EpsilonForge site.

### Architecture

The docs site is built with Sphinx into a static `site/` directory, then
deployed with [SST](https://sst.dev) (Ion) to an `sst.aws.StaticSite` that is
attached to the shared EpsilonForge CloudFront distribution ("Router") served
by the private website infrastructure repo. The site is mounted at the path
`/palace-toolkit`.

### Files involved

| File | Purpose |
|------|---------|
| `sst.config.ts` | SST app definition: app config, AWS provider, Router lookup, StaticSite definition. |
| `package.json` | Declares `sst` devDependency and `deploy:docs` / `diff:docs` scripts. |
| `sst-env.d.ts` | Auto-generated SST type declarations (gitignored). |
| `sst.pyi`, `packages/.../sst.pyi` | Auto-generated SST Python type stubs. |
| `.sst/` | SST local state (gitignored). |
| `.github/workflows/docs.yml` | CI: builds docs, then deploys on `main`. |
| `.gitignore` | Ignores Node/SST tooling (`node_modules/`, `.sst/`, `sst-env.d.ts`, `package-lock.json`). |

### One-time setup

1. Install deploy dependencies:

   ```bash
   npm install
   python -m pip install sphinx pydata-sphinx-theme myst-parser myst-nb sphinx-copybutton sphinx-design linkify-it-py
   ```

2. Set environment variables:

   ```bash
   export EPSILON_FORGE_ROUTER_DISTRIBUTION_ID="<router-distribution-id>"
   export AWS_REGION="us-east-2"
   ```

   The `EPSILON_FORGE_ROUTER_DISTRIBUTION_ID` value comes from the private repo
   stack output `routerDistributionId`.

### sst.config.ts

```ts
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
          ? { region: awsRegion, profile: awsProfile }
          : { region: awsRegion },
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
      path: "site",
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
```

### Local deploy

```bash
npx sst deploy --stage production
```

Use `npx sst diff --stage production` to preview changes before deploying.

### GitHub Actions deploy (docs.yml)

The `deploy-docs` job assumed an IAM role via OIDC, read the shared Router
distribution ID from AWS SSM Parameter Store, then ran `sst deploy`.

Environment variables used:

- `SST_STAGE`: `production` on `main`, otherwise `pr-<number>`.
- `AWS_ACCOUNT_ID`: from `vars['EPSILON_FORGE_AWS_ACCOUNT_ID']`, default `527097962874`.
- `AWS_REGION`: `us-east-2`.

Deploy steps (condensed):

```yaml
- name: Configure AWS credentials via OIDC
  uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: arn:aws:iam::${{ env.AWS_ACCOUNT_ID }}:role/epsilon-forge-palace-toolkit-docs-deploy-${{ env.SST_STAGE }}
    aws-region: ${{ env.AWS_REGION }}

- name: Resolve shared router distribution ID
  run: |
    PARAMETER_NAME="/epsilon-forge/$SST_STAGE/router-distribution-id"
    ROUTER_DISTRIBUTION_ID="$(aws ssm get-parameter --name "$PARAMETER_NAME" --query 'Parameter.Value' --output text)"

- name: Install deploy dependencies
  run: npm install --no-fund --no-audit

- name: Deploy docs
  env:
    EPSILON_FORGE_ROUTER_DISTRIBUTION_ID: ${{ steps.router.outputs.router_distribution_id }}
  run: npx sst deploy --stage "$SST_STAGE"
```

### Infrastructure assumptions

To reproduce this in another package you need the private EpsilonForge website
infrastructure to provide:

- A CloudFront **Router** distribution; its ID is exported as
  `routerDistributionId` in the stack outputs.
- A deterministic deploy IAM role per stage:
  - Role name pattern: `epsilon-forge-<project>-docs-deploy-<stage>`
- The Router distribution ID published to AWS SSM Parameter Store:
  - SSM parameter pattern: `/epsilon-forge/<stage>/router-distribution-id`
- AWS account has an IAM OIDC provider for
  `https://token.actions.githubusercontent.com`.
  - For account `527097962874`, provider ARN:
    `arn:aws:iam::527097962874:oidc-provider/token.actions.githubusercontent.com`
- The deploy role trust policy allows `sts:AssumeRoleWithWebIdentity` for this
  repository. For pushes to `main`, the subject should match:
  `repo:EpsilonForge/PalaceToolkit:ref:refs/heads/main`

## 2. GitHub Pages

The docs are now deployed to GitHub Pages. On every push to `main` (and
manually via `workflow_dispatch`), the `docs.yml` workflow builds the Sphinx
site and publishes `site/` with the `actions/deploy-pages` action.

### One-time setup

1. Build the site locally to confirm it works:

   ```bash
   pip install -e ".[docs]"
   just ipykernel
   just docs-full
   ```

2. In the GitHub repository settings:
   **Settings → Pages → Build and deployment → Source: GitHub Actions.**

3. Push the updated workflow to `main` (or trigger it manually from the
   Actions tab). The site appears at
   `https://<owner>.github.io/<repository>/`.

### Workflow

See `.github/workflows/docs.yml`. Key points:

- `permissions.pages: write` and `permissions.id-token: write` are required.
- The `build-docs` job uploads `site/` with `actions/upload-pages-artifact`.
- The `deploy-docs` job runs `actions/deploy-pages` in the `github-pages`
  environment, gated on `main`.

### Local preview

```bash
just serve   # http://localhost:8080
```