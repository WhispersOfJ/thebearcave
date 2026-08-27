# Internal helper: live container names for tab completion.
function __stack_containers
    docker ps -a --format '{{.Names}}' 2>/dev/null | sort
end
