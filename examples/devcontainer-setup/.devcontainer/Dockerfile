FROM node:20-bullseye

# Install system dependencies needed for claude-cognitive
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    git \
    curl \
    vim \
    jq \
    && rm -rf /var/lib/apt/lists/*

# The devcontainer feature will install Claude Code
# We just need to ensure Python is available for claude-cognitive scripts

USER node
WORKDIR /home/node

# Set up environment
ENV PATH="/home/node/.local/bin:${PATH}"
ENV CLAUDE_INSTANCE="${CLAUDE_INSTANCE:-docker}"

CMD ["/bin/bash"]
