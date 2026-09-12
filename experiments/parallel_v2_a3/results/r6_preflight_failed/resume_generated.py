def resume(self, todo, visited):
    started = time.monotonic()
    while todo or any((self.observations[c] and c not in self.cleared for c in range(1, 21))):
        if self.config.get('joint_scheduling', False):
            pending = [c for c in range(1, 21) if self.observations[c] and c not in self.cleared]
            index = self.next_station(todo) if todo else None
            if pending:
                ch = min(pending, key=lambda c: _di_dist(self.position, _di_enclosing_circle(self.polygons[c])[0]))
                target = _di_enclosing_circle(self.polygons[ch])[0]
                source_cost = _di_dist(self.position, target) * self.config.get('source_priority', 1.0)
                station_cost = _di_dist(self.position, self.points[index]) if index is not None else float('inf')
                if source_cost <= station_cost:
                    self.localize(ch)
                    if self.config.get('upper_bound_stop', True) and len(self.cleared) >= 16:
                        break
                    continue
            self.scan_station(index, defer=True)
            visited.append(index)
            todo.remove(index)
            if self.config.get('upper_bound_stop', True) and len(self.cleared) >= 16:
                break
            continue
        index = self.next_station(todo)
        self.scan_station(index)
        visited.append(index)
        todo.remove(index)
        if self.config.get('upper_bound_stop', True) and len(self.cleared) >= 16:
            break
    unresolved = [c for c in range(1, 21) if c not in self.cleared]
    count_certificate = len(self.cleared) >= 16
    geometric_certificate = all((not self.observations[c] and len(self.scanned[c]) == len(self.points) for c in unresolved))
    certificate = count_certificate or geometric_certificate
    if not certificate:
        raise RuntimeError('Search ended without complete coverage certificate')
    final = self._accept(self.env.exit())
    return {'mode': self.mode, 'cleared_count': len(self.cleared), 'cleared_channels': sorted(self.cleared), 'virtual_time_s': self.virtual_time, 'average_time_s': self.virtual_time / max(1, len(self.cleared)), 'program_time_s': time.monotonic() - started, 'coverage_complete': certificate, 'completion_certified': certificate, 'geometric_coverage_complete': geometric_certificate, 'coverage_point_count': len(self.points), 'visited_points': visited, 'certificate_type': 'known_count_upper_bound' if count_certificate else 'complete_geometric_coverage', 'unresolved_channels_certified_absent': unresolved, 'counters': dict(self.counters), 'exit_response': final}
