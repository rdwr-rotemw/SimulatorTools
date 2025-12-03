# Build stage
FROM node:18-alpine AS build
WORKDIR /app

# Accept build arguments from docker-compose
ARG REACT_APP_API_BASE_URL
ARG REACT_APP_API_TIMEOUT

# Set as environment variables for the build
ENV REACT_APP_API_BASE_URL=$REACT_APP_API_BASE_URL
ENV REACT_APP_API_TIMEOUT=$REACT_APP_API_TIMEOUT

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build production React app
RUN npm run build

# Production stage - serve with simple HTTP server
FROM node:18-alpine
WORKDIR /app

# Install serve to host the build
RUN npm install -g serve

# Copy built files from build stage
COPY --from=build /app/build ./build

# Expose port 3000
EXPOSE 3000

# Serve the build on port 3000
CMD ["serve", "-s", "build", "-l", "3000"]

