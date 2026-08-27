function stack-image-check --description 'Show Docker image versions'
    fmt_heading "Docker Image Versions"
    echo ""
    docker ps --format '{{.Names}}\t{{.Image}}' | sort | while read -l name image
        echo "  $name  $image"
    end
end
