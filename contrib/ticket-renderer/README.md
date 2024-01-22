# Coriolis Ticket Renderer

When a new ticket needs to be rendered, Coriolis will:

- Create a temporary directory (`$TMPDIR`) with:
    - `render.json`: ticket metadata and personalization details,
    - Extra assets (images uploaded by users, etc).
- Run a container you specify in the ticket type configuration with:
    - `podman` if available, `docker` otherwise
    - `run --interactive --tty --rm`
    - `--pull never` (container must be present on the Coriolis worker machine already)
    - `-v $TMPDIR:/render` (mount that temp dir under `/render`)
    - `-w /render` (start work in `/render`)
    - `--network none` (prevents any network access)
    - `--user 1000:1000` (always as user 1000:1000)
    - `--security-opt "no-new-privileges:true"` (disables setuid/setgid escalation)
    - The default entrypoint/command.
- Copy `render.png` from that temporary directory as the rendered image.

Your container must create the `render.png` file. Use `CMD ["any-command"]` in your Dockerfile to specify the default
entrypoint to execute. After successful execution, the temporary directory is deleted.

`render.json` contains a JSON object with the following structure:

- `render` (dict): Extra details for a specified render job.
    - `variant`: Ticket variant to render (`front`, `back`, etc).
    - `image` (str): **Optional.** Personalized image or other asset uploaded by a user. Contains the file name that
      will be present in `/render`.
- `ticket` (dict): Details for a specific ticket type.
    - `code` (int): Numeric code for a specific ticket, without its prefix.
    - `prefixed_code` (int): Rendered code with a prefix, as a string.
    - `flags` (list[str]): All flags on this ticket (per-ticket + type flags).
    - `nickname` (str): **Optional.** Personalized ticket nickname.
    - `age_gate` (bool): Is the user of age (>18)?
    - `name` (str): Long, usually formal ticket owner name.
    - `email` (str): **Optional.** Ticket owner email (if available).
    - `phone` (str): **Optional.** Ticket owner phone number (if available).
- `ticket_type` (dict): Details shared between all tickets of a given type.
    - `name` (str): Long, human-readable ticket name.
    - `color` (str): Assigned role color, in a CSS-friendly format (`#rrggbb` or `rgba()`).
    - `short_name` (str): Short name, often used as a role label on the ticket.
    - `flags` (list[str]): List of flags common for all tickets of this type.
    - `code_prefix` (str): Prefix for all ticket codes of this type. **May be empty, but not null.**
- `event` (dict): Details shared between all tickets for this event.
    - `name` (str): Event name.

## Example

Example Dockerfiles and scripts for multiple FBT events are provided in this directory. They use Chromium and Jinja2 to
create a HTML document, then render it as a screenshot to the required image.

- Every renderer uses the `EVENT.Dockerfile` script which builds the `EVENT-renderer` image.
- In all cases, `template-EVENT` directory is copied to `/template` in each image.
- The `test-input` directory contains files that Coriolis would generate and mount under `/render`.
- The `test-output` directory will be created with all render artifacts - this must contain the final `render.png`.
- `./build-image.sh EVENT` rebuilds a given event renderer according to the convention above.
- `./test-render.sh EVENT [JOB]` sets up the test environment in `test-output` and runs a render job.
- Convenient template dev helper: `./watch-template.sh EVENT [JOB]`
    - Whenever anything in `template-EVENT` changes, runs `./build-image.sh EVENT && ./test-render.sh EVENT JOB`
    - Which you could run yourself like this: `./build-image.sh viii-tm && ./test-render.sh viii-tm jobs/std-front.json`
- Results should be in: `test-output/render.png`
