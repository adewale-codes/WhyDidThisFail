// The three example logs offered on the landing page for a one-click try.
// Same fixtures used to verify the Phase 1 pattern database, so each one is
// guaranteed to produce a fast, pattern-matched result -- a reliable demo.

export interface ExampleLog {
  id: string;
  label: string;
  format: string;
  log: string;
}

export const EXAMPLE_LOGS: ExampleLog[] = [
  {
    id: "python",
    label: "Python: ModuleNotFoundError",
    format: "python",
    log: `$ python manage.py runserver
Watching for file changes with StatReloader
Performing system checks...

Traceback (most recent call last):
  File "manage.py", line 22, in <module>
    main()
  File "manage.py", line 18, in main
    execute_from_command_line(sys.argv)
  File "/home/dev/venv/lib/python3.11/site-packages/django/core/management/__init__.py", line 442, in execute_from_command_line
    utility.execute()
  File "/home/dev/venv/lib/python3.11/site-packages/django/core/management/__init__.py", line 436, in execute
    self.fetch_command(subcommand).run_from_argv(self.argv)
  File "/home/dev/project/app/urls.py", line 3, in <module>
    import requests_oauthlib
ModuleNotFoundError: No module named 'requests_oauthlib'
`,
  },
  {
    id: "npm",
    label: "npm: ERESOLVE dependency conflict",
    format: "npm",
    log: `npm ERR! code ERESOLVE
npm ERR! ERESOLVE unable to resolve dependency tree
npm ERR!
npm ERR! While resolving: my-app@0.1.0
npm ERR! Found: react@18.2.0
npm ERR! node_modules/react
npm ERR!   react@"^18.2.0" from the root project
npm ERR!
npm ERR! Could not resolve dependency:
npm ERR! peer react@"^17.0.0" from react-beautiful-dnd@13.1.1
npm ERR! node_modules/react-beautiful-dnd
npm ERR!   react-beautiful-dnd@"^13.1.1" from the root project
npm ERR!
npm ERR! Fix the upstream dependency conflict, or retry
npm ERR! this command with --force or --legacy-peer-deps
npm ERR! to accept an incorrect (and potentially broken) dependency resolution.
npm ERR!
npm ERR! A complete log of this run can be found in:
npm ERR!     /home/dev/.npm/_logs/2026-09-09T10_12_44_112Z-debug-0.log
`,
  },
  {
    id: "docker",
    label: "Docker: RUN step failure",
    format: "docker",
    log: `#1 [internal] load build definition from Dockerfile
#1 transferring dockerfile: 312B done
#1 DONE 0.0s

#4 [1/7] FROM docker.io/library/node:20-slim
#4 CACHED

#7 [3/7] COPY package.json package-lock.json ./
#7 CACHED

#8 [4/7] RUN npm ci
#8 0.412 npm ERR! code EUSAGE
#8 0.413 npm ERR!
#8 0.413 npm ERR! \`npm ci\` can only install packages when your package.json and package-lock.json or npm-shrinkwrap.json are in sync. Please update your lock file with \`npm install\` before continuing.
#8 0.414 npm ERR!
#8 0.414 npm ERR! Missing: nanoid@5.0.7 from lock file
#8 0.415 npm ERR!
#8 0.415 npm ERR! A complete log of this run can be found in: /root/.npm/_logs/2026-09-09T09_58_02_331Z-debug-0.log
#8 ERROR: process "/bin/sh -c npm ci" did not complete successfully: exit code: 1
------
 > [4/7] RUN npm ci:
0.412 npm ERR! code EUSAGE
0.413 npm ERR!
0.413 npm ERR! \`npm ci\` can only install packages when your package.json and package-lock.json or npm-shrinkwrap.json are in sync. Please update your lock file with \`npm install\` before continuing.
0.414 npm ERR!
0.414 npm ERR! Missing: nanoid@5.0.7 from lock file
------
Dockerfile:7
--------------------
   5 |     COPY package.json package-lock.json ./
   6 |
   7 | >>> RUN npm ci
   8 |
   9 |     COPY . .
--------------------
ERROR: failed to solve: process "/bin/sh -c npm ci" did not complete successfully: exit code: 1
`,
  },
];
