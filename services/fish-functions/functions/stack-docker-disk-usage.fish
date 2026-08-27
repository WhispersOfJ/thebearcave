function stack-docker-disk-usage --description 'Show Docker disk usage'
    fmt_heading "Docker Disk Usage"
    echo ""
    docker system df
end
