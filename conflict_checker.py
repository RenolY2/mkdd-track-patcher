class Conflicts(object):
    def __init__(self):
        self._conflict_candidates = {}
        self.conflict_appeared = False 
        
    def add_conflict(self, identifier, source):
        if identifier not in self._conflict_candidates:
            self._conflict_candidates[identifier] = set()
            self._conflict_candidates[identifier].add(source)
        else:
            self._conflict_candidates[identifier].add(source)
            self.conflict_appeared = True 
    
    def get_conflicts(self):
        conflicts = []
        for key, conflict in self._conflict_candidates.items():
            if len(conflict) > 1:
                if conflict not in conflicts:
                    conflicts.append(conflict)
        
        mark_for_deletion = []
        
        for i in range(len(conflicts)):
            for j in range(i+1, len(conflicts)):
                c1 = conflicts[i]
                c2 = conflicts[j]
                if c1 < c2:
                    mark_for_deletion.append(i)
                elif c2 < c1:
                    mark_for_deletion.append(j)
        
        new_conflicts = []
        for i, v in enumerate(conflicts):
            if i not in mark_for_deletion:
                new_conflicts.append(v)
        
        return new_conflicts 
        
if __name__ == "__main__":
    conflict = Conflicts()
    
    conflict.add_conflict("A", "Hey its me")
    conflict.add_conflict("B", "Hey its me")
    conflict.add_conflict("C", "Hey its me")
    conflict.add_conflict("A", "Hey its not me")
    conflict.add_conflict("B", "Hey its not me")
    conflict.add_conflict("B", "Hey its also not me")
    conflict.add_conflict("C", "Hey its not me")
    conflict.add_conflict("C", "Hey its also not me")
    conflict.add_conflict("C", "Hey its also not me 2")
    print(conflict.get_conflicts())