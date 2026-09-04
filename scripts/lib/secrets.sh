#!/usr/bin/env bash
# Secrets management for The Bear Cave setup.
# Sources: scripts/lib/helpers.sh

create_secrets_dir() {
    log_info "Creating secrets directory..."
    mkdir -p "$SECRETS_DIR"
    chmod 700 "$SECRETS_DIR"
    log_success "Secrets directory created"
}

generate_secrets() {
    log_info "Generating Docker secrets..."

    local secrets=(
        "plex_token"
        "radarr_api_key"
        "sonarr_api_key"
        "prowlarr_api_key"
        "frontend_backend_api_key"
        "nzbdav_webdav_user"
        "nzbdav_webdav_pass"
        "nzbdav_rclone_rc_pass"
        "nzbdav_profile_token"
        "nzbdav_usenet_host"
        "nzbdav_usenet_user"
        "nzbdav_usenet_pass"
        "nzbdav_usenet_backup_host"
        "nzbdav_usenet_backup_user"
        "nzbdav_usenet_backup_pass"
    )

    for secret in "${secrets[@]}"; do
        local secret_file="$SECRETS_DIR/$secret"

        if [ ! -f "$secret_file" ]; then
            local value
            value=$(generate_secret 32)
            echo -n "$value" > "$secret_file"
            chmod 600 "$secret_file"
            log_info "Generated secret: $secret"
        else
            log_info "Secret already exists: $secret"
        fi
    done

    log_success "All active-stack secrets generated"
}

generate_recyclarr_secrets() {
    log_info "Generating Recyclarr secrets (config/recyclarr/secrets.yml)..."

    mkdir -p "config/recyclarr"

    if [ ! -f "$ENV_FILE" ]; then
        log_warning "Skipping Recyclarr secrets: $ENV_FILE missing"
        return 0
    fi

    local radarr_key sonarr_key
    radarr_key=$(awk -F= '/^RADARR_API_KEY=/{print $2; exit}' "$ENV_FILE" | tr -d '"' | tr -d "'")
    sonarr_key=$(awk -F= '/^SONARR_API_KEY=/{print $2; exit}' "$ENV_FILE" | tr -d '"' | tr -d "'")

    if [ -z "$radarr_key" ] || [ -z "$sonarr_key" ]; then
        log_warning "Skipping Recyclarr secrets: RADARR_API_KEY/SONARR_API_KEY missing from $ENV_FILE"
        return 0
    fi

    cat > "config/recyclarr/secrets.yml" <<EOF
radarr_apikey: $radarr_key
sonarr_apikey: $sonarr_key
EOF
    chmod 600 "config/recyclarr/secrets.yml"
    log_success "Recyclarr secrets generated"
}
