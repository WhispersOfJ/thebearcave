function stack-watchstate-status --description 'WatchState sync state, tracked items, import schedule'
    __watchstate_api GET "v1/api/state"
end
