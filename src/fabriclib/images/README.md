# fabriclib/images

Container images on the host (design [2.6.2](../../../docs/volume_2_technologies_and_features/2.6.2-image-updates.md#2621-status), D21).
Every image is pinned by digest; the validated list is `config/images.lock.yaml`
of the installed fabric. Nothing here runs on its own: a fabric upgrade keeps
the images a host runs, and only `fabricctl images update` moves them.

| File | What |
|---|---|
| `constants.py` | Managed services in update order (unit, container, image var, local build) and the rollback state file |
| `installed_services.py` | The managed services this install has |
| `built_from.py` | The base a local fabric image was built FROM (its `org.fabric.base` label) |
| `needs_rebuild.py` | Whether a compose file's local image is missing or built from another base than its pinned one |
| `running_image.py` | What a service runs now (container image, or the base of its local build) |
| `image_status.py` | Per service: running, set, validated, and the state (current / update available / held / …) |
| `switch_image.py` | Move a service (and any sharing its base) to a ref: pull, render, compose down/up per service, health-gated, rolled back on failure |
| `update_images.py` | Move services to their validated images (skips images the admin set, unless forced) |
| `rollback_image.py` | Back to the image before the last update |
| `prune_images.py` | Remove old images of fabric's repositories: not pinned, not the rollback image, not used by any container |
| `run_images_command.py` | `fabricctl images status / update / rollback / prune` |
