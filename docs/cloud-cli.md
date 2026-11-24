# EnergyChain Cloud CLI

The Cloud CLI is available from the EnergyChain source checkout. Local SDK execution and EnGraph development do not require this CLI or a Cloud account.

## Install

With Python 3.10 or newer, create and activate a virtual environment. From the EnergyChain SDK checkout, run these commands.

```sh
python -m pip install -e ".[cloud]"
python -m pip install "energygraph>=0.2,<0.3"
```

The Cloud extra uses Windows Credential Locker, macOS Keychain or Linux Secret Service. Unlock your desktop credential store before signing in.

## Link and push a workflow

Run your graph locally first. In the trusted application directory, run the following commands. The browser confirms a short code using your account on the selected Cloud site.

```sh
energychain auth login
energychain projects list
energychain project link <project-id>
energychain workflow push --app workflow.py:graph
energychain workflow deploy
```

Use a project returned by `projects list`. The CLI checks that the grant matches the environment of the selected website. Deployment uses the environment of the local project link.

The CLI defaults to production at `https://cloud.energychain.app`. To use staging, set `EC_CLOUD_ORIGIN` to `https://staging.energychain.app` or pass `--cloud-origin` before each command.

```sh
energychain --cloud-origin https://staging.energychain.app auth login
energychain --cloud-origin https://staging.energychain.app projects list
```

If you used the old CLI while staging ran at `cloud.energychain.app`, sign in and link the project again on `staging.energychain.app`. The CLI uses hostname-qualified project and workflow files in `.energychain` and a separate OS credential store entry for each site. Run `energychain auth logout` on the selected site to revoke its credential.

Push takes one UTF-8 Python file of up to 32 KiB that exports one EnGraph `Graph` or `CompiledGraph` as `graph`. It runs the trusted local file to compile the topology. Cloud receives the source artifact for isolated execution and an allowlisted graph definition for Studio. Keep credentials out of source files, graph labels and route names.

`workflow push` registers an immutable revision and makes its graph available in Studio. Identical pushes resolve to the same revision. Set `--name` to choose a stable Cloud name, or omit it to use the graph ID when it satisfies Cloud naming rules. Use `workflow deploy --name <name> --revision <number>` to activate a specific registered revision. Without a name, deployment uses the last push in the linked folder.

Open Studio on your selected Cloud site to inspect the graph. After deployment, run the workflow and inspect the recorded execution and EnSmith evidence in Runs and Tracing.
