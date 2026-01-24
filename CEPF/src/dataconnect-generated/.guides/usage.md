# Basic Usage

Always prioritize using a supported framework over using the generated SDK
directly. Supported frameworks simplify the developer experience and help ensure
best practices are followed.





## Advanced Usage
If a user is not using a supported framework, they can use the generated SDK directly.

Here's an example of how to use it with the first 5 operations:

```js
import { createUser, getUserById, createExperience, listExperiencesByUser } from '@dataconnect/generated';


// Operation CreateUser: 
const { data } = await CreateUser(dataConnect);

// Operation GetUserById:  For variables, look at type GetUserByIdVars in ../index.d.ts
const { data } = await GetUserById(dataConnect, getUserByIdVars);

// Operation CreateExperience:  For variables, look at type CreateExperienceVars in ../index.d.ts
const { data } = await CreateExperience(dataConnect, createExperienceVars);

// Operation ListExperiencesByUser:  For variables, look at type ListExperiencesByUserVars in ../index.d.ts
const { data } = await ListExperiencesByUser(dataConnect, listExperiencesByUserVars);


```