function __host_containers
    docker ps -a --format '{{.Names}}' 2>/dev/null | sort
end
