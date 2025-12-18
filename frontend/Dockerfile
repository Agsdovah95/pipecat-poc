# Builder stage
FROM node:22-alpine AS builder

# Set the working directory
WORKDIR /app

# Copy the package.json and install dependencies
COPY package.json .
RUN npm install

# Copy the source code
COPY . .

# Build the application
RUN npm run build

# Production stage
FROM nginx:stable-alpine

# Remove the default configuration
RUN rm -rf /etc/nginx/conf.d

# Copy the custom configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy the built application
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose the port
EXPOSE 80

# Start the server
CMD ["nginx", "-g", "daemon off;"]