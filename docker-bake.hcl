# Multi-arch builds (NFR-17): arm64 for the ASUS GX10 / Apple Silicon,
# amd64 for typical cloud servers.
#
#   docker buildx create --use --name domo   # once
#   docker buildx bake --push                 # build both arches and push
#   docker buildx bake --set '*.platform=linux/arm64' --load   # one arch, local

variable "IMAGE_PREFIX" { default = "ghcr.io/stanleyhughes/majordomo" }
variable "IMAGE_TAG"    { default = "latest" }

target "_common" {
  platforms = ["linux/amd64", "linux/arm64"]
}

group "default" { targets = ["agent", "backend", "web"] }

target "agent" {
  inherits = ["_common"]
  context  = "agent"
  tags     = ["${IMAGE_PREFIX}-agent:${IMAGE_TAG}"]
}

target "backend" {
  inherits = ["_common"]
  context  = "backend"
  tags     = ["${IMAGE_PREFIX}-backend:${IMAGE_TAG}"]
}

target "web" {
  inherits = ["_common"]
  context  = "web"
  tags     = ["${IMAGE_PREFIX}-web:${IMAGE_TAG}"]
}
